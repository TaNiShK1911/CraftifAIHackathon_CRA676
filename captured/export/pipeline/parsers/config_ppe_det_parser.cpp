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

extern "C" bool ParseConfigPpeDet(
    std::vector<NvDsInferLayerInfo> const& outputLayersInfo,
    NvDsInferNetworkInfo const& networkInfo,
    NvDsInferParseDetectionParams const& detectionParams,
    std::vector<NvDsInferObjectDetectionInfo>& objectList);

CHECK_CUSTOM_PARSE_FUNC_PROTOTYPE(ParseConfigPpeDet);

extern "C" bool ParseConfigPpeDet(
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
        fprintf(stderr, "[PPE_DET] first call: layer=%s numDims=%d "
                "networkInput=%.0fx%.0f numClasses=%u outputs=%zu\n",
                layer0.layerName ? layer0.layerName : "?",
                layer0.inferDims.numDims, netW, netH, numClasses,
                outputLayersInfo.size());
    }

    // ==== BEGIN GENERATED DECODE ====
    // Engine output shape (with batch stripped): [10, 8400]
    // inferDims: numDims=2, d[0]=10, d[1]=8400
    // Layout: rows = 4 box coords + numClasses scores, cols = proposals
    // We need to identify which dim is the "feature" dim (== 4 + numClasses)
    // and which is the "count" dim (number of proposals).

    const unsigned dim0 = layer0.inferDims.d[0]; // 10
    const unsigned dim1 = layer0.inferDims.d[1]; // 8400

    const unsigned featureSize = 4u + numClasses; // 10

    // Determine layout: is data [featureSize x numProposals] or [numProposals x featureSize]?
    bool transposed = false; // if true, data is [numProposals x featureSize] already
    unsigned numProposals = 0;

    if (dim0 == featureSize && dim1 != featureSize) {
        // [featureSize x numProposals] — YOLOv8 native ONNX layout
        numProposals = dim1;
        transposed = false;
    } else if (dim1 == featureSize && dim0 != featureSize) {
        // [numProposals x featureSize] — already transposed
        numProposals = dim0;
        transposed = true;
    } else if (dim0 == featureSize && dim1 == featureSize) {
        // Ambiguous square — treat as [featureSize x numProposals]
        numProposals = dim1;
        transposed = false;
    } else {
        fprintf(stderr, "[PPE_DET] ERROR: unexpected dims d[0]=%u d[1]=%u featureSize=%u\n",
                dim0, dim1, featureSize);
        return false;
    }

    for (unsigned i = 0; i < numProposals; ++i) {
        // Read cx, cy, w, h and class scores depending on layout
        float cx, cy, bw, bh;
        if (!transposed) {
            // Column-major for proposals: row r, col i => data[r * numProposals + i]
            cx = data[0u * numProposals + i];
            cy = data[1u * numProposals + i];
            bw = data[2u * numProposals + i];
            bh = data[3u * numProposals + i];
        } else {
            // Row-major: row i, col c => data[i * featureSize + c]
            cx = data[i * featureSize + 0u];
            cy = data[i * featureSize + 1u];
            bw = data[i * featureSize + 2u];
            bh = data[i * featureSize + 3u];
        }

        // Find best class
        float maxScore = -1.0f;
        unsigned bestClass = 0;
        for (unsigned c = 0; c < numClasses; ++c) {
            float score;
            if (!transposed) {
                score = data[(4u + c) * numProposals + i];
            } else {
                score = data[i * featureSize + 4u + c];
            }
            if (score > maxScore) {
                maxScore = score;
                bestClass = c;
            }
        }

        // Threshold — scores are post-sigmoid probabilities from YOLOv8 export
        float thr = (bestClass < detectionParams.perClassPreclusterThreshold.size())
                     ? detectionParams.perClassPreclusterThreshold[bestClass]
                     : 0.3f;
        if (maxScore < thr) continue;

        // Convert cx,cy,w,h (in network-input pixel coords) to left,top,width,height
        float left   = cx - bw * 0.5f;
        float top    = cy - bh * 0.5f;
        float right  = cx + bw * 0.5f;
        float bottom = cy + bh * 0.5f;

        // Clamp to network input
        left   = std::max<float>(0.0f, std::min<float>(left,   netW));
        top    = std::max<float>(0.0f, std::min<float>(top,    netH));
        right  = std::max<float>(0.0f, std::min<float>(right,  netW));
        bottom = std::max<float>(0.0f, std::min<float>(bottom, netH));

        float finalW = right - left;
        float finalH = bottom - top;
        if (finalW <= 1.0f || finalH <= 1.0f) continue;

        NvDsInferObjectDetectionInfo obj;
        obj.classId = bestClass;
        obj.left = left;
        obj.top = top;
        obj.width = finalW;
        obj.height = finalH;
        obj.detectionConfidence = maxScore;
        objectList.push_back(obj);
    }
    // ==== END GENERATED DECODE ====
    return true;
}