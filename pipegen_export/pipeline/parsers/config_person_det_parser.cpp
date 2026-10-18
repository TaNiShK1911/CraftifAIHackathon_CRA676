// Custom detection (bbox) parser (generated).
// Scaffold validates the output layer and exposes the raw tensor(s); the DECODE
// block (per-model) populates `objectList` with NvDsInferObjectDetectionInfo.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "nvdsinfer_custom_impl.h"

extern "C" bool ParseConfigPersonDet(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList);

CHECK_CUSTOM_PARSE_FUNC_PROTOTYPE(ParseConfigPersonDet);

extern "C" bool ParseConfigPersonDet(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList)
{
    if (outputLayersInfo.empty()) return false;
    auto const& layer0 = outputLayersInfo[0];

    const unsigned numClasses = detectionParams.numClassesConfigured;
    const float netW = static_cast<float>(networkInfo.width);
    const float netH = static_cast<float>(networkInfo.height);
    const float* data = static_cast<const float*>(layer0.buffer);

    static bool logged = false;
    if (!logged) {
        logged = true;
        fprintf(stderr, "[PersonDet] first call: layer=%s numDims=%d "
                "networkInput=%.0fx%.0f numClasses=%u outputs=%zu\n",
                layer0.layerName ? layer0.layerName : "?",
                layer0.inferDims.numDims, netW, netH, numClasses,
                outputLayersInfo.size());
    }

    // ==== BEGIN GENERATED DECODE ====
    // YOLO11s output shape from engine: [1, 84, 8400]
    // After batch dim stripped: inferDims numDims=2, d[0]=84, d[1]=8400
    // Layout: 84 x N where 84 = 4 box coords + 80 class scores
    // We need to transpose logically: for proposal j, box coords are at
    // data[row * N + j] for row 0..3, class scores at rows 4..83.

    const unsigned int featureDim = layer0.inferDims.d[0]; // 84
    const unsigned int numProposals = layer0.inferDims.d[1]; // 8400

    if (featureDim < 4u + numClasses) {
        fprintf(stderr, "[PersonDet] ERROR: featureDim %u < 4 + numClasses %u\n",
                featureDim, numClasses);
        return false;
    }

    // We only emit class 0 (person). Collect candidates, then run NMS.
    struct RawDet {
        float cx, cy, w, h, score;
    };
    std::vector<RawDet> candidates;
    candidates.reserve(512);

    const unsigned targetClass = 0; // person

    float thr = 0.35f;
    if (targetClass < detectionParams.perClassPreclusterThreshold.size()) {
        thr = detectionParams.perClassPreclusterThreshold[targetClass];
    }

    for (unsigned j = 0; j < numProposals; ++j) {
        // Find best class score across all 80 classes
        // But we only care about class 0 (person). However, we still check
        // if class 0 is the argmax or at least above threshold.
        // Per the job notes: FILTER TO CLASS 0 ONLY.
        // The scores are post-sigmoid (ultralytics YOLO11 export).
        float personScore = data[(4u + targetClass) * numProposals + j];
        if (personScore < thr) continue;

        // Also check that person is the best class for this proposal
        // (optional but reduces false positives).
        bool isBest = true;
        for (unsigned c = 0; c < numClasses; ++c) {
            if (c == targetClass) continue;
            if (data[(4u + c) * numProposals + j] > personScore) {
                isBest = false;
                break;
            }
        }
        if (!isBest) continue;

        float cx = data[0u * numProposals + j];
        float cy = data[1u * numProposals + j];
        float bw = data[2u * numProposals + j];
        float bh = data[3u * numProposals + j];

        RawDet rd;
        rd.cx = cx;
        rd.cy = cy;
        rd.w = bw;
        rd.h = bh;
        rd.score = personScore;
        candidates.push_back(rd);
    }

    // Sort by score descending for greedy NMS
    std::sort(candidates.begin(), candidates.end(),
              [](const RawDet& a, const RawDet& b) { return a.score > b.score; });

    const float nmsThresh = 0.45f;
    std::vector<bool> suppressed(candidates.size(), false);

    for (size_t i = 0; i < candidates.size(); ++i) {
        if (suppressed[i]) continue;
        const RawDet& a = candidates[i];
        float ax1 = a.cx - a.w * 0.5f;
        float ay1 = a.cy - a.h * 0.5f;
        float ax2 = a.cx + a.w * 0.5f;
        float ay2 = a.cy + a.h * 0.5f;
        float aArea = a.w * a.h;

        // Emit this detection
        {
            float left   = std::max(ax1, 0.0f);
            float top    = std::max(ay1, 0.0f);
            float right  = std::min(ax2, netW);
            float bottom = std::min(ay2, netH);
            float w = right - left;
            float h = bottom - top;
            if (w > 1.0f && h > 1.0f) {
                NvDsInferObjectDetectionInfo obj;
                obj.classId = targetClass;
                obj.left = left;
                obj.top = top;
                obj.width = w;
                obj.height = h;
                obj.detectionConfidence = a.score;
                objectList.push_back(obj);
            }
        }

        // Suppress overlapping lower-score boxes
        for (size_t k = i + 1; k < candidates.size(); ++k) {
            if (suppressed[k]) continue;
            const RawDet& b = candidates[k];
            float bx1 = b.cx - b.w * 0.5f;
            float by1 = b.cy - b.h * 0.5f;
            float bx2 = b.cx + b.w * 0.5f;
            float by2 = b.cy + b.h * 0.5f;

            float ix1 = std::max(ax1, bx1);
            float iy1 = std::max(ay1, by1);
            float ix2 = std::min(ax2, bx2);
            float iy2 = std::min(ay2, by2);
            float iw = std::max(ix2 - ix1, 0.0f);
            float ih = std::max(iy2 - iy1, 0.0f);
            float inter = iw * ih;
            float bArea = b.w * b.h;
            float unionArea = aArea + bArea - inter;
            if (unionArea > 0.0f && (inter / unionArea) > nmsThresh) {
                suppressed[k] = true;
            }
        }
    }
    // ==== END GENERATED DECODE ====
    return true;
}