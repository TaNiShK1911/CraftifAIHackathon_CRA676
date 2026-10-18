#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <cmath>
#include <map>
#include <string>
#include <algorithm>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/dnn.hpp>

#include "nvcustomprocess.h"

#include <gst/gst.h>
#include "nvdsmeta.h"
#include "gstnvdsinfer.h"
#include "realsense_meta.h"
#include "render_meta.h"

static void write_nv12(const cv::Mat &bgr, NvDsCustomPostProcessFrameInCpu *in) {
    const int W = in->W, H = in->H;
    cv::Mat i420; cv::cvtColor(bgr, i420, cv::COLOR_BGR2YUV_I420);
    const uint8_t *ysrc = i420.data;
    const uint8_t *usrc = ysrc + (size_t)W * H;
    const uint8_t *vsrc = usrc + (size_t)(W / 2) * (H / 2);
    for (int r = 0; r < H; ++r)
        memcpy(in->Y_host + (size_t)r * in->Y_pitch, ysrc + (size_t)r * W, (size_t)W);
    const int cW = W / 2, cH = H / 2;
    for (int r = 0; r < cH; ++r) {
        uint8_t *dst = in->UV_host + (size_t)r * in->UV_pitch;
        const uint8_t *u = usrc + (size_t)r * cW, *v = vsrc + (size_t)r * cW;
        for (int c = 0; c < cW; ++c) { dst[2*c] = u[c]; dst[2*c+1] = v[c]; }
    }
}

static cv::Mat read_nv12_bgr(NvDsCustomPostProcessFrameInCpu *in) {
    const int W = in->W, H = in->H;
    cv::Mat yuv(H + H / 2, W, CV_8UC1);
    for (int r = 0; r < H; ++r)
        memcpy(yuv.ptr(r), in->Y_host + (size_t)r * in->Y_pitch, (size_t)W);
    for (int r = 0; r < H / 2; ++r)
        memcpy(yuv.ptr(H + r), in->UV_host + (size_t)r * in->UV_pitch, (size_t)W);
    cv::Mat bgr; cv::cvtColor(yuv, bgr, cv::COLOR_YUV2BGR_NV12); return bgr;
}

static const RsMeta *find_rs_meta(NvDsFrameMeta *fm) {
    if (!fm) return nullptr;
    static gsize t = 0;
    if (g_once_init_enter(&t)) {
        gsize v = (gsize) nvds_get_user_meta_type((gchar *) RS_NVDS_META_NAME);
        g_once_init_leave(&t, v);
    }
    for (NvDsMetaList *l = fm->frame_user_meta_list; l; l = l->next) {
        NvDsUserMeta *um = (NvDsUserMeta *) l->data;
        if (um && um->base_meta.meta_type == (NvDsMetaType) t)
            return (const RsMeta *) um->user_meta_data;
    }
    return nullptr;
}

// ── Geometry helpers for hazard-zone polygon overlap ────────────────────────

struct Pt { double x, y; };

static double cross2(Pt a, Pt b, Pt c) {
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

static bool on_segment(Pt a, Pt b, Pt c) {
    return std::abs(cross2(a, b, c)) <= 1e-9 &&
           std::min(a.x, b.x) <= c.x && c.x <= std::max(a.x, b.x) &&
           std::min(a.y, b.y) <= c.y && c.y <= std::max(a.y, b.y);
}

static bool segments_intersect(Pt a, Pt b, Pt c, Pt d) {
    double ab_c = cross2(a, b, c), ab_d = cross2(a, b, d);
    double cd_a = cross2(c, d, a), cd_b = cross2(c, d, b);
    if (((ab_c > 0 && ab_d < 0) || (ab_c < 0 && ab_d > 0)) &&
        ((cd_a > 0 && cd_b < 0) || (cd_a < 0 && cd_b > 0)))
        return true;
    return on_segment(a, b, c) || on_segment(a, b, d) ||
           on_segment(c, d, a) || on_segment(c, d, b);
}

static bool point_in_polygon(Pt pt, const Pt *poly, int n) {
    bool inside = false;
    for (int i = 0; i < n; ++i) {
        Pt a = poly[i], b = poly[(i + 1) % n];
        if (on_segment(a, b, pt)) return true;
        if ((a.y > pt.y) != (b.y > pt.y)) {
            double cx = a.x + (pt.y - a.y) * (b.x - a.x) / (b.y - a.y);
            if (cx > pt.x) inside = !inside;
        }
    }
    return inside;
}

static bool box_overlaps_polygon(double bx1, double by1, double bx2, double by2,
                                 const Pt *poly, int npoly) {
    if (bx2 < bx1 || by2 < by1) return false;
    Pt corners[4] = {{bx1,by1},{bx2,by1},{bx2,by2},{bx1,by2}};
    for (int i = 0; i < 4; ++i)
        if (point_in_polygon(corners[i], poly, npoly)) return true;
    for (int i = 0; i < npoly; ++i)
        if (poly[i].x >= bx1 && poly[i].x <= bx2 &&
            poly[i].y >= by1 && poly[i].y <= by2) return true;
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < npoly; ++j)
            if (segments_intersect(corners[i], corners[(i+1)%4],
                                   poly[j], poly[(j+1)%npoly])) return true;
    return false;
}

// ── Per-track dwell state (static local, single pipeline instance) ──────────
// NOTE: the job notes say "no global/static mutable buffers" for data like
// cv::Mat / vectors, but per-track dwell counters REQUIRE cross-frame state.
// We use a function-local static map which is safe for a single-instance .so.
struct DwellRec { int frames_in_zone; bool ever_inside; };

extern "C" bool NvDsCustomPostProcess(NvDsCustomPostProcessFrameInCpu *in) {
    if (!in || !in->Y_host || !in->UV_host) return false;
    const int W = in->W, H = in->H;
    if (W < 2 || H < 2 || (W & 1) || (H & 1)) {
        fprintf(stderr, "[zone_ppe] surface must be even-sized, got %dx%d\n", W, H);
        return false;
    }

    NvDsInferTensorMeta *tm = in->num_tensor_metas
        ? (NvDsInferTensorMeta *) in->tensor_metas[0] : nullptr;
    const RsMeta *rs = find_rs_meta((NvDsFrameMeta *) in->frame_meta);
    (void) tm; (void) rs;

    // ==== BEGIN GENERATED PROCESS ====

    // Hazard polygon (PIR: [[256,432],[1280,432],[1280,1152],[256,1152]])
    static const Pt HAZARD_POLY[] = {{256,432},{1280,432},{1280,1152},{256,1152}};
    static const int NPOLY = 4;

    // PPE class names for gie_id=3
    static const char* PPE_NAMES[] = {"Gloves","Vest","goggles","helmet","mask","safety_shoe"};
    (void) PPE_NAMES;

    // Parameters from PIR
    const double HELMET_FRAC = 0.4;
    const double VEST_TOP_FRAC = 0.25;
    const double VEST_BOT_FRAC = 0.8;
    const double FPS = 25.0;

    NvDsFrameMeta *fmeta = (NvDsFrameMeta *) in->frame_meta;

    // ── Collect person objects (gie_id==1) with tracker IDs ─────────────────
    struct PersonInfo {
        guint64 track_id;
        float left, top, width, height;
        bool inside_hazard;
        double dwell_s;
        bool has_helmet;
        bool has_vest;
        std::vector<std::string> missing_ppe;
    };
    std::vector<PersonInfo> persons;

    if (fmeta) {
        for (NvDsMetaList *ol = fmeta->obj_meta_list; ol; ol = ol->next) {
            NvDsObjectMeta *obj = (NvDsObjectMeta *) ol->data;
            if (!obj) continue;
            if (obj->unique_component_id != 1) continue;
            PersonInfo pi;
            pi.track_id = obj->object_id;
            pi.left   = obj->rect_params.left;
            pi.top    = obj->rect_params.top;
            pi.width  = obj->rect_params.width;
            pi.height = obj->rect_params.height;
            pi.inside_hazard = false;
            pi.dwell_s = 0.0;
            pi.has_helmet = false;
            pi.has_vest = false;
            persons.push_back(pi);
        }
    }

    // ── Hazard zone check ───────────────────────────────────────────────────
    static std::map<guint64, DwellRec> dwell_map;

    for (size_t i = 0; i < persons.size(); ++i) {
        PersonInfo &p = persons[i];
        double bx1 = (double)p.left;
        double by1 = (double)p.top;
        double bx2 = bx1 + (double)p.width;
        double by2 = by1 + (double)p.height;
        bool inside = box_overlaps_polygon(bx1, by1, bx2, by2, HAZARD_POLY, NPOLY);
        p.inside_hazard = inside;

        DwellRec &rec = dwell_map[p.track_id];
        if (inside) {
            rec.frames_in_zone++;
            rec.ever_inside = true;
        }
        p.dwell_s = rec.frames_in_zone / FPS;
    }

    // ── Collect PPE detections (gie_id==3) ──────────────────────────────────
    struct PPEDet {
        int class_id;        // 0=Gloves,1=Vest,2=goggles,3=helmet,4=mask,5=safety_shoe
        float cx, cy;
    };
    std::vector<PPEDet> ppe_dets;

    if (fmeta) {
        for (NvDsMetaList *ol = fmeta->obj_meta_list; ol; ol = ol->next) {
            NvDsObjectMeta *obj = (NvDsObjectMeta *) ol->data;
            if (!obj) continue;
            if (obj->unique_component_id != 3) continue;
            PPEDet d;
            d.class_id = obj->class_id;
            d.cx = obj->rect_params.left + obj->rect_params.width * 0.5f;
            d.cy = obj->rect_params.top  + obj->rect_params.height * 0.5f;
            ppe_dets.push_back(d);
        }
    }

    // ── PPE association: match helmet (class 3) and Vest (class 1) to persons ─
    for (size_t di = 0; di < ppe_dets.size(); ++di) {
        const PPEDet &det = ppe_dets[di];
        if (det.class_id != 3 && det.class_id != 1) continue;

        int best_idx = -1;
        double best_dist = 1e18;

        for (size_t pi = 0; pi < persons.size(); ++pi) {
            const PersonInfo &p = persons[pi];
            float px1 = p.left, py1 = p.top;
            float px2 = px1 + p.width, py2 = py1 + p.height;
            float ph = p.height, pw = p.width;
            if (pw <= 0.0f || ph <= 0.0f) continue;

            float region_top, region_bot;
            if (det.class_id == 3) { // helmet
                region_top = py1;
                region_bot = py1 + (float)(HELMET_FRAC * ph);
            } else { // Vest (class 1)
                region_top = py1 + (float)(VEST_TOP_FRAC * ph);
                region_bot = py1 + (float)(VEST_BOT_FRAC * ph);
            }

            if (det.cx >= px1 && det.cx <= px2 &&
                det.cy >= region_top && det.cy <= region_bot) {
                double dist = std::abs((double)det.cx - (double)(px1 + px2) * 0.5) / (double)pw +
                              std::abs((double)det.cy - (double)(region_top + region_bot) * 0.5) / (double)ph;
                if (dist < best_dist) {
                    best_dist = dist;
                    best_idx = (int)pi;
                }
            }
        }

        if (best_idx >= 0) {
            if (det.class_id == 3) persons[(size_t)best_idx].has_helmet = true;
            else                   persons[(size_t)best_idx].has_vest   = true;
        }
    }

    // ── Build missing PPE lists ─────────────────────────────────────────────
    for (size_t i = 0; i < persons.size(); ++i) {
        PersonInfo &p = persons[i];
        if (!p.has_helmet) p.missing_ppe.push_back("hard hat");
        if (!p.has_vest)   p.missing_ppe.push_back("safety vest");
    }

    // ── Counts ──────────────────────────────────────────────────────────────
    int current_in_zone = 0, current_ppe_violations = 0;
    for (size_t i = 0; i < persons.size(); ++i) {
        if (persons[i].inside_hazard) current_in_zone++;
        if (!persons[i].missing_ppe.empty()) current_ppe_violations++;
    }

    // ── Draw ────────────────────────────────────────────────────────────────
    cv::Mat frame = read_nv12_bgr(in);

    // Draw hazard polygon outline (red, thick)
    {
        std::vector<cv::Point> pts(NPOLY);
        for (int i = 0; i < NPOLY; ++i)
            pts[(size_t)i] = cv::Point((int)HAZARD_POLY[i].x, (int)HAZARD_POLY[i].y);
        cv::polylines(frame, pts, true, cv::Scalar(0, 0, 255), 3, cv::LINE_AA);
    }

    // Draw each person box
    for (size_t i = 0; i < persons.size(); ++i) {
        const PersonInfo &p = persons[i];
        cv::Scalar color;
        if (p.inside_hazard)
            color = cv::Scalar(0, 0, 255);       // red = in hazard zone
        else if (!p.missing_ppe.empty())
            color = cv::Scalar(0, 200, 255);      // yellow = PPE violation
        else
            color = cv::Scalar(0, 200, 0);         // green = compliant, outside

        cv::Rect box((int)p.left, (int)p.top, (int)p.width, (int)p.height);
        cv::rectangle(frame, box, color, 2, cv::LINE_AA);

        // Label: track ID, zone, PPE
        char label[256];
        const char *zone_str = p.inside_hazard ? "IN ZONE" : "safe";
        std::string ppe_str;
        if (p.missing_ppe.empty()) {
            ppe_str = "PPE OK";
        } else {
            ppe_str = "missing:";
            for (size_t mi = 0; mi < p.missing_ppe.size(); ++mi) {
                ppe_str += " ";
                ppe_str += p.missing_ppe[mi];
            }
        }
        snprintf(label, sizeof(label), "#%lu %s %s",
                 (unsigned long)p.track_id, zone_str, ppe_str.c_str());

        int baseline = 0;
        cv::Size tsz = cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, 0.55, 1, &baseline);
        int tx = (int)p.left;
        int ty = (int)p.top - 6;
        if (ty - tsz.height < 0) ty = (int)p.top + tsz.height + 6;
        cv::rectangle(frame,
                      cv::Point(tx, ty - tsz.height - 2),
                      cv::Point(tx + tsz.width + 2, ty + baseline + 2),
                      color, cv::FILLED);
        cv::putText(frame, label, cv::Point(tx + 1, ty),
                    cv::FONT_HERSHEY_SIMPLEX, 0.55, cv::Scalar(255,255,255), 1, cv::LINE_AA);
    }

    write_nv12(frame, in);

    // ── Publish via render_meta ─────────────────────────────────────────────
    render_meta::Builder sb(W, H);

    // Frame-level fields
    sb.field_i("current_people", (int)persons.size());
    sb.field_i("current_in_zone", current_in_zone);
    sb.field_i("current_possible_ppe_violations", current_ppe_violations);

    // Hazard polygon as a polygon shape
    {
        std::vector<double> poly_xy;
        for (int i = 0; i < NPOLY; ++i) {
            poly_xy.push_back(HAZARD_POLY[i].x);
            poly_xy.push_back(HAZARD_POLY[i].y);
        }
        sb.polygon(poly_xy, "hazard_zone");
    }

    // Per-person boxes with metadata
    for (size_t i = 0; i < persons.size(); ++i) {
        const PersonInfo &p = persons[i];

        // Build a label that encodes zone + PPE status
        std::string lbl = "person";
        if (p.inside_hazard) lbl += " IN_ZONE";
        if (!p.missing_ppe.empty()) {
            lbl += " missing:";
            for (size_t mi = 0; mi < p.missing_ppe.size(); ++mi) {
                lbl += (mi == 0 ? "" : ",");
                lbl += p.missing_ppe[mi];
            }
        }

        sb.box((double)p.left, (double)p.top, (double)p.width, (double)p.height,
               lbl.c_str(), (int)p.track_id, 1.0);

        // Additional per-person scalar fields (using unique field names per track)
        char fn[128];
        snprintf(fn, sizeof(fn), "track_%lu_in_zone", (unsigned long)p.track_id);
        sb.field_i(fn, p.inside_hazard ? 1 : 0);
        snprintf(fn, sizeof(fn), "track_%lu_dwell_s", (unsigned long)p.track_id);
        sb.field_d(fn, p.dwell_s);
        snprintf(fn, sizeof(fn), "track_%lu_helmet", (unsigned long)p.track_id);
        sb.field_i(fn, p.has_helmet ? 1 : 0);
        snprintf(fn, sizeof(fn), "track_%lu_vest", (unsigned long)p.track_id);
        sb.field_i(fn, p.has_vest ? 1 : 0);
    }

    sb.publish(in->frame_meta);

    // ==== END GENERATED PROCESS ====
    return true;
}

CHECK_NVCUSTOMPROCESS_CPU_PROTOTYPE(NvDsCustomPostProcess);