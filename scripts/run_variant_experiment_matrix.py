#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

AGENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = AGENT_ROOT / "scripts"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from learning.log2knowledge import process_run_record
from learning.report_token_roi import write_token_roi_reports
from memory.run_db import append_jsonl as append_run_record
from memory.run_db import run_db_path
from runtime_paths import resolve_runtime_paths
from run_design_evolve_loop import build_metric_vector, composite_score, legality_ok


DEFAULT_CASES = [
    "aes_nangate45",
    "ibex_nangate45",
    "jpeg_nangate45",
    "ariane133_nangate45",
    "bp_quad_nangate45",
]


@dataclass(frozen=True)
class VariantSpec:
    name: str
    family: str
    touched_symbol: str
    summary: str
    apply: Callable[[Path], list[str]]
    algorithmic_changes: tuple[str, ...] = ()
    source_family: str = "clean_evolve_base"
    startpoint: str = "clean_evolve_base"
    entrypoint_contract: str = "detailed_placement_evolve -use_negotiation"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def replace_once(path: Path, old: str, new: str) -> None:
    text = read_text(path)
    if old not in text:
        raise RuntimeError(f"Pattern not found in {path}: {old!r}")
    write_text(path, text.replace(old, new, 1))


def replace_all(path: Path, old: str, new: str) -> None:
    text = read_text(path)
    if old not in text:
        raise RuntimeError(f"Pattern not found in {path}: {old!r}")
    write_text(path, text.replace(old, new))


def replace_cpp_function(path: Path, signature: str, replacement: str) -> None:
    text = read_text(path)
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"C++ function signature not found in {path}: {signature!r}")
    brace = text.find("{", start + len(signature))
    if brace < 0:
        raise RuntimeError(f"C++ function body not found in {path}: {signature!r}")

    depth = 0
    end = None
    for index in range(brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise RuntimeError(f"C++ function body was not balanced in {path}: {signature!r}")
    write_text(path, text[:start] + replacement + text[end:])


def variant_file(src: Path, relative: str) -> Path:
    path = src / "src" / relative
    if not path.is_file():
        raise RuntimeError(f"Missing expected dpl_evolve file: {path}")
    return path


def mutate_greedy1(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.cpp")
    replace_once(path, "  // greedyImprove(1);\n", "  greedyImprove(1);\n")
    return [str(path)]


def mutate_greedy2(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.cpp")
    replace_once(path, "  // greedyImprove(1);\n", "  greedyImprove(2);\n")
    return [str(path)]


def mutate_search_narrow_runtime(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.h")
    replace_once(path, "constexpr int kHorizWindow = 20;", "constexpr int kHorizWindow = 16;")
    replace_once(path, "constexpr int kAdjWindow = 5;", "constexpr int kAdjWindow = 4;")
    return [str(path)]


def mutate_search_wide_escape(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.h")
    replace_once(path, "constexpr int kHorizWindow = 20;", "constexpr int kHorizWindow = 24;")
    replace_once(path, "constexpr int kAdjWindow = 5;", "constexpr int kAdjWindow = 6;")
    return [str(path)]


def mutate_large_design_diamond_fallback(src: Path) -> list[str]:
    path = variant_file(src, "Opendp.cpp")
    replace_once(
        path,
        "  } else {\n    initGrid();",
        "  } else {\n"
        "    constexpr size_t kLargeDesignFallbackCells = 500000;\n"
        "    if (network_ != nullptr\n"
        "        && network_->getNodes().size() >= kLargeDesignFallbackCells) {\n"
        "      logger_->warn(DPL,\n"
        "                    1803,\n"
        "                    \"Large-design runtime fallback: {} nodes exceeds \"\n"
        "                    \"the negotiation threshold {}; running diamond DPL \"\n"
        "                    \"behind the common evolve entrypoint.\",\n"
        "                    network_->getNodes().size(),\n"
        "                    kLargeDesignFallbackCells);\n"
        "      diamondDPL();\n"
        "      findDisplacementStats();\n"
        "      updateDbInstLocations();\n"
        "      return;\n"
        "    }\n"
        "    initGrid();",
    )
    return [str(path)]


RUN_NEGOTIATION_ACTIVE_SET_ORIGINAL = """  // Seed with illegal cells and all movable neighbors within the search
  // window so the loop can create space organically.
  std::unordered_set<int> active_set(illegalCells.begin(), illegalCells.end());

  for (int idx : illegalCells) {
    const NegCell& seed = cells_[idx];
    const int xlo = seed.x - horiz_window_;
    const int xhi = seed.x + seed.width + horiz_window_;
    const int ylo = seed.y - adj_window_;
    const int yhi = seed.y + seed.height + adj_window_;

    for (int i = 0; i < static_cast<int>(cells_.size()); ++i) {
      if (cells_[i].fixed) {
        continue;
      }
      const NegCell& nb = cells_[i];
      if (nb.x >= xlo && nb.x <= xhi && nb.y >= ylo && nb.y <= yhi) {
        active_set.insert(i);
      }
    }
  }

  std::vector<int> active(active_set.begin(), active_set.end());
"""


RUN_NEGOTIATION_ROW_BUCKET_ACTIVE_SET = """  // Seed with illegal cells plus movable cells found through per-row spatial
  // buckets.  The old path scanned every cell for every illegal seed, which
  // becomes O(illegal_cells * cells).  Here each movable cell is indexed once
  // into the rows it occupies, and every seed only scans bounded x-ranges in
  // nearby rows.
  std::unordered_set<int> active_set(illegalCells.begin(), illegalCells.end());

  std::vector<std::vector<std::pair<int, int>>> row_buckets(grid_h_);
  for (int i = 0; i < static_cast<int>(cells_.size()); ++i) {
    if (cells_[i].fixed) {
      continue;
    }
    const NegCell& cell = cells_[i];
    const int row_begin = std::clamp(cell.y, 0, grid_h_);
    const int row_end
        = std::clamp(cell.y + std::max(1, cell.height), 0, grid_h_);
    for (int row = row_begin; row < row_end; ++row) {
      row_buckets[row].emplace_back(cell.x, i);
    }
  }
  for (auto& row : row_buckets) {
    std::ranges::sort(row, [](const auto& a, const auto& b) {
      if (a.first != b.first) {
        return a.first < b.first;
      }
      return a.second < b.second;
    });
  }

  int bucket_candidates = 0;
  int bucket_candidate_caps = 0;
  constexpr int kRowBucketMaxCandidatesPerSeed = 512;
  for (int idx : illegalCells) {
    if (idx < 0 || idx >= static_cast<int>(cells_.size())) {
      continue;
    }
    const NegCell& seed = cells_[idx];
    const int xlo = seed.x - horiz_window_;
    const int xhi = seed.x + seed.width + horiz_window_;
    const int ylo = std::max(0, seed.y - adj_window_);
    const int yhi = std::min(grid_h_ - 1, seed.y + seed.height + adj_window_);
    if (ylo > yhi) {
      continue;
    }

    int seed_bucket_candidates = 0;
    bool seed_cap_hit = false;
    for (int row = ylo; row <= yhi; ++row) {
      const auto& bucket = row_buckets[row];
      const int bucket_backtrack = std::max(horiz_window_, 4);
      const int min_start_x = xlo - bucket_backtrack;
      const int max_start_x = xhi + bucket_backtrack;
      auto it = std::lower_bound(
          bucket.begin(), bucket.end(), min_start_x, [](const auto& entry, int x) {
            return entry.first < x;
          });
      for (; it != bucket.end() && it->first <= max_start_x; ++it) {
        if (++seed_bucket_candidates > kRowBucketMaxCandidatesPerSeed) {
          ++bucket_candidate_caps;
          seed_cap_hit = true;
          break;
        }
        const int nb_idx = it->second;
        const NegCell& nb = cells_[nb_idx];
        ++bucket_candidates;
        if (nb.x <= xhi && nb.x + nb.width >= xlo && nb.y <= yhi
            && nb.y + nb.height >= ylo) {
          active_set.insert(nb_idx);
        }
      }
      if (seed_cap_hit) {
        break;
      }
    }
  }

  logger_->metric("negotiation__active_set__illegal_seeds",
                  static_cast<int>(illegalCells.size()));
  logger_->metric("negotiation__active_set__bucket_candidates",
                  bucket_candidates);
  logger_->metric("negotiation__active_set__bucket_candidate_caps",
                  bucket_candidate_caps);

  std::vector<int> active(active_set.begin(), active_set.end());
  logger_->metric("negotiation__active_set__active_cells",
                  static_cast<int>(active.size()));
"""


FIND_BEST_DRC_PENALTY_ORIGINAL = """  const double kDrcPenalty = 1e3 * (1.0 + iter);
"""


FIND_BEST_DRC_PENALTY_CAPPED = """  const double kDrcPenalty = 1e3 * (1.0 + iter);
  constexpr size_t kLargeDesignCandidateCapCells = 100000;
  constexpr int kLargeDesignMaxCandidatesPerCell = 256;
  const bool large_design_candidate_cap
      = cells_.size() >= kLargeDesignCandidateCapCells;
  const int search_dx_step
      = large_design_candidate_cap ? std::max(1, horiz_window_ / 5) : 1;
  int candidate_budget_seen = 0;
"""


FIND_BEST_ANCHOR_INSERT_ORIGINAL = """  // Search around the initial (GP) position.
"""


FIND_BEST_ANCHOR_INSERT_CAPPED = """  // Candidate cap mode keeps large designs on the same negotiation path, but
  // avoids evaluating every horizontal site in both dense windows.  Always
  // probe exact anchors so the sampled x-stride cannot skip home/current sites.
  tryLocation(cell.init_x, cell.init_y);
  tryLocation(cell.x, cell.y);

  // Search around the initial (GP) position.
"""


FIND_BEST_INIT_LOOP_ORIGINAL = """    for (int dy = -adj_window_; dy <= adj_window_; ++dy) {
      for (int dx = -horiz_window_; dx <= horiz_window_; ++dx) {
        tryLocation(cell.init_x + dx, cell.init_y + dy);
      }
    }
"""


FIND_BEST_INIT_LOOP_CAPPED = """    for (int dy = -adj_window_; dy <= adj_window_; ++dy) {
      for (int dx = -horiz_window_; dx <= horiz_window_; dx += search_dx_step) {
        tryLocation(cell.init_x + dx, cell.init_y + dy);
      }
    }
"""


FIND_BEST_CURRENT_LOOP_ORIGINAL = """    for (int dy = -adj_window_; dy <= adj_window_; ++dy) {
      for (int dx = -horiz_window_; dx <= horiz_window_; ++dx) {
        tryLocation(cell.x + dx, cell.y + dy);
      }
    }
"""


FIND_BEST_CURRENT_LOOP_CAPPED = """    for (int dy = -adj_window_; dy <= adj_window_; ++dy) {
      for (int dx = -horiz_window_; dx <= horiz_window_; dx += search_dx_step) {
        tryLocation(cell.x + dx, cell.y + dy);
      }
    }
"""


FIND_BEST_TRY_LOCATION_ORIGINAL = """  auto tryLocation = [&](int tx, int ty) {
    {
      utl::DebugScopedTimer t(prof_filter_s_);
"""


FIND_BEST_TRY_LOCATION_CAPPED = """  auto tryLocation = [&](int tx, int ty) {
    if (large_design_candidate_cap
        && candidate_budget_seen >= kLargeDesignMaxCandidatesPerCell) {
      ++prof_candidates_filtered_;
      return;
    }
    ++candidate_budget_seen;
    {
      utl::DebugScopedTimer t(prof_filter_s_);
"""


NEGOTIATION_ITER_BYSTANDER_SCAN_ORIGINAL = """  // Scan all movable cells for newly-created DRC violations outside the
  // current active set.  This handles cases where a move in the active
  // set created a one-site gap (or other DRC issue) with a bystander.
  {
    utl::DebugScopedTimer t(bystander_s);
    for (int i = 0; i < static_cast<int>(cells_.size()); ++i) {
      if (cells_[i].fixed || active_set.contains(i)) {
        continue;
      }
      if (!isCellLegal(i)) {
        activeCells.push_back(i);
        active_set.insert(i);
        ++totalOverflow;
      }
    }
  }
"""


NEGOTIATION_ITER_DIRTY_REGION_SCAN = """  // Scan dirty regions touched by the active frontier for newly-created DRC
  // violations outside the active set.  Small designs keep the exact scan;
  // large designs use row buckets and caps so bystander repair cannot become
  // an every-cell DRC walk each iteration.
  {
    utl::DebugScopedTimer t(bystander_s);
    constexpr size_t kDirtyScanLargeDesignCells = 100000;
    constexpr int kDirtyScanHaloRows = 1;
    constexpr int kDirtyScanHaloSites = 2;
    constexpr int kDirtyScanMaxSeeds = 8192;
    constexpr int kDirtyScanMaxCandidates = 50000;
    const bool use_dirty_scan = cells_.size() >= kDirtyScanLargeDesignCells;

    if (!use_dirty_scan) {
      for (int i = 0; i < static_cast<int>(cells_.size()); ++i) {
        if (cells_[i].fixed || active_set.contains(i)) {
          continue;
        }
        if (!isCellLegal(i)) {
          activeCells.push_back(i);
          active_set.insert(i);
          ++totalOverflow;
        }
      }
    } else {
      struct DirtyRect
      {
        int xlo;
        int xhi;
        int ylo;
        int yhi;
      };

      std::vector<DirtyRect> dirty_rects;
      dirty_rects.reserve(
          std::min(activeCells.size(),
                   static_cast<size_t>(kDirtyScanMaxSeeds)));
      int dirty_seed_count = 0;
      for (int idx : activeCells) {
        if (idx < 0 || idx >= static_cast<int>(cells_.size())
            || cells_[idx].fixed) {
          continue;
        }
        if (dirty_seed_count >= kDirtyScanMaxSeeds) {
          break;
        }
        const NegCell& cell = cells_[idx];
        dirty_rects.push_back(
            {std::max(0, effXBegin(cell) - kDirtyScanHaloSites),
             std::min(grid_w_, effXEnd(cell) + kDirtyScanHaloSites),
             std::max(0, cell.y - kDirtyScanHaloRows),
             std::min(grid_h_, cell.y + cell.height + kDirtyScanHaloRows + 1)});
        ++dirty_seed_count;
      }

      std::vector<std::vector<std::pair<int, int>>> row_buckets(grid_h_);
      for (int i = 0; i < static_cast<int>(cells_.size()); ++i) {
        if (cells_[i].fixed || active_set.contains(i)) {
          continue;
        }
        const NegCell& cell = cells_[i];
        const int row_begin = std::clamp(cell.y, 0, grid_h_);
        const int row_end
            = std::clamp(cell.y + std::max(1, cell.height), 0, grid_h_);
        for (int row = row_begin; row < row_end; ++row) {
          row_buckets[row].emplace_back(cell.x, i);
        }
      }
      for (auto& row : row_buckets) {
        std::ranges::sort(row, [](const auto& a, const auto& b) {
          if (a.first != b.first) {
            return a.first < b.first;
          }
          return a.second < b.second;
        });
      }

      int dirty_candidates = 0;
      int dirty_added = 0;
      bool dirty_candidate_cap_hit = false;
      for (const DirtyRect& rect : dirty_rects) {
        if (dirty_candidate_cap_hit) {
          break;
        }
        if (rect.xlo >= rect.xhi || rect.ylo >= rect.yhi) {
          continue;
        }
        const int bucket_backtrack
            = std::max(horiz_window_ + kDirtyScanHaloSites, 128);
        const int min_start_x = rect.xlo - bucket_backtrack;
        const int max_start_x = rect.xhi + kDirtyScanHaloSites;
        for (int row = rect.ylo; row < rect.yhi; ++row) {
          const auto& bucket = row_buckets[row];
          auto it = std::lower_bound(
              bucket.begin(),
              bucket.end(),
              min_start_x,
              [](const auto& entry, int x) { return entry.first < x; });
          for (; it != bucket.end() && it->first <= max_start_x; ++it) {
            if (++dirty_candidates > kDirtyScanMaxCandidates) {
              dirty_candidate_cap_hit = true;
              break;
            }
            const int nb_idx = it->second;
            if (active_set.contains(nb_idx)) {
              continue;
            }
            const NegCell& nb = cells_[nb_idx];
            if (!(nb.x < rect.xhi && nb.x + nb.width > rect.xlo
                  && nb.y < rect.yhi && nb.y + nb.height > rect.ylo)) {
              continue;
            }
            if (!isCellLegal(nb_idx)) {
              activeCells.push_back(nb_idx);
              active_set.insert(nb_idx);
              ++totalOverflow;
              ++dirty_added;
            }
          }
          if (dirty_candidate_cap_hit) {
            break;
          }
        }
      }
      logger_->metric("negotiation__dirty_scan__seed_cells",
                      dirty_seed_count);
      logger_->metric("negotiation__dirty_scan__candidates",
                      dirty_candidates);
      logger_->metric("negotiation__dirty_scan__added_cells", dirty_added);
      logger_->metric("negotiation__dirty_scan__candidate_cap_hit",
                      dirty_candidate_cap_hit ? 1 : 0);
    }
  }
"""


def mutate_row_bucket_active_set(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_once(
        path,
        RUN_NEGOTIATION_ACTIVE_SET_ORIGINAL,
        RUN_NEGOTIATION_ROW_BUCKET_ACTIVE_SET,
    )
    replace_once(path, FIND_BEST_DRC_PENALTY_ORIGINAL, FIND_BEST_DRC_PENALTY_CAPPED)
    replace_once(path, FIND_BEST_TRY_LOCATION_ORIGINAL, FIND_BEST_TRY_LOCATION_CAPPED)
    replace_once(path, FIND_BEST_ANCHOR_INSERT_ORIGINAL, FIND_BEST_ANCHOR_INSERT_CAPPED)
    replace_once(path, FIND_BEST_INIT_LOOP_ORIGINAL, FIND_BEST_INIT_LOOP_CAPPED)
    replace_once(path, FIND_BEST_CURRENT_LOOP_ORIGINAL, FIND_BEST_CURRENT_LOOP_CAPPED)
    replace_once(
        path,
        NEGOTIATION_ITER_BYSTANDER_SCAN_ORIGINAL,
        NEGOTIATION_ITER_DIRTY_REGION_SCAN,
    )
    return [str(path)]


mutate_negotiation_row_bucket_active_set = mutate_row_bucket_active_set


def mutate_disable_diamond_stall_fallback(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_once(
        path,
        """        logger_->warn(
            utl::DPL,
            700,
            "Negotiation phase 1: overflow stuck at {} for 3 consecutive "
            "iterations.\\nUsing old diamond search for remaining cells.",
            phase_1_overflows);
        diamondRecovery(active);
""",
        """        logger_->warn(utl::DPL,
                      700,
                      "Negotiation phase 1: overflow stuck at {} for 3 "
                      "consecutive iterations; continuing without fallback.",
                      phase_1_overflows);
""",
    )
    replace_once(
        path,
        """        logger_->warn(utl::DPL,
                      702,
                      "Negotiation phase 2: overflow stuck at {} for 3 "
                      "consecutive iterations.",
                      phase_2_overflows);
        diamondRecovery(active);
""",
        """        logger_->warn(utl::DPL,
                      702,
                      "Negotiation phase 2: overflow stuck at {} for 3 "
                      "consecutive iterations; stopping without fallback.",
                      phase_2_overflows);
""",
    )
    return [str(path)]


def mutate_net_anchor_quality_frontier(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_once(
        path,
        """  auto best_cost = static_cast<double>(kInfCost);
  int best_x = cell.x;
""",
        """  auto best_cost = static_cast<double>(kInfCost);
  auto best_cheap_cost = static_cast<double>(kInfCost);
  int best_x = cell.x;
""",
    )
    replace_once(
        path,
        """  // Look up the DPL Node once for DRC checks (may be null if no
  // Opendp integration is available).
  Node* node = (opendp_ && opendp_->drc_engine_ && network_)
                   ? network_->getNode(cell.db_inst)
                   : nullptr;

  // DRC penalty escalates with iteration count: early iterations are
""",
        """  // Look up the DPL Node once for DRC checks (may be null if no
  // Opendp integration is available).
  Node* node = (opendp_ && opendp_->drc_engine_ && network_)
                   ? network_->getNode(cell.db_inst)
                   : nullptr;

  double net_anchor_x = 0.0;
  double net_anchor_y = 0.0;
  int net_anchor_samples = 0;
  if (node != nullptr && site_width_ > 0 && row_height_ > 0) {
    constexpr int kHpwlGuardMaxPinsPerNet = 64;
    constexpr int kHpwlGuardMaxSamples = 96;
    std::unordered_set<const Edge*> visited_edges;
    for (const Pin* pin : node->getPins()) {
      const Edge* edge = pin->getEdge();
      if (edge == nullptr || edge->getNumPins() <= 1
          || edge->getNumPins() > kHpwlGuardMaxPinsPerNet
          || !visited_edges.insert(edge).second) {
        continue;
      }
      odb::Rect peer_box;
      peer_box.mergeInit();
      bool has_peer = false;
      for (const Pin* edge_pin : edge->getPins()) {
        const Node* pin_node = edge_pin->getNode();
        if (pin_node == nullptr || pin_node == node) {
          continue;
        }
        const int peer_x = pin_node->getCenterX().v + edge_pin->getOffsetX().v;
        const int peer_y = pin_node->getCenterY().v + edge_pin->getOffsetY().v;
        peer_box.merge(odb::Point(peer_x, peer_y));
        has_peer = true;
      }
      if (!has_peer) {
        continue;
      }
      net_anchor_x
          += static_cast<double>(peer_box.xMin() + peer_box.xMax())
             / (2.0 * static_cast<double>(site_width_));
      net_anchor_y
          += static_cast<double>(peer_box.yMin() + peer_box.yMax())
             / (2.0 * static_cast<double>(row_height_));
      if (++net_anchor_samples >= kHpwlGuardMaxSamples) {
        break;
      }
    }
    if (net_anchor_samples > 0) {
      net_anchor_x /= static_cast<double>(net_anchor_samples);
      net_anchor_y /= static_cast<double>(net_anchor_samples);
    }
  }

  auto netAnchorDelta = [&](int tx, int ty) -> double {
    if (net_anchor_samples == 0) {
      return 0.0;
    }
    const double current_x = static_cast<double>(cell.x) + 0.5 * cell.width;
    const double current_y = static_cast<double>(cell.y) + 0.5 * cell.height;
    const double target_x = static_cast<double>(tx) + 0.5 * cell.width;
    const double target_y = static_cast<double>(ty) + 0.5 * cell.height;
    const double current_dist
        = std::abs(current_x - net_anchor_x) + std::abs(current_y - net_anchor_y);
    const double target_dist
        = std::abs(target_x - net_anchor_x) + std::abs(target_y - net_anchor_y);
    return target_dist - current_dist;
  };

  // DRC penalty escalates with iteration count: early iterations are
""",
    )
    replace_once(
        path,
        """  int candidate_budget_seen = 0;
""",
        """  int candidate_budget_seen = 0;
  constexpr int kQualityFrontierCap = 24;
  constexpr double kQualityFrontierAbsMargin = 2.0;
  constexpr double kQualityFrontierRelMargin = 0.03;
  int quality_frontier_evals = 0;
""",
    )
    replace_once(
        path,
        """    // Add a DRC penalty so clean positions are strongly preferred,
""",
        """    const int candidate_disp = std::abs(tx - cell.init_x) + std::abs(ty - cell.init_y);
    const int outlier_excess
        = std::max(0,
                   candidate_disp
                       - std::max(max_disp_threshold_,
                                  2 * horiz_window_ + adj_window_));
    cost += 0.05 * static_cast<double>(outlier_excess * outlier_excess);

    // Add a DRC penalty so clean positions are strongly preferred,
""",
    )
    replace_once(
        path,
        """    ++prof_candidates_evaluated_;
    if (cost < best_cost) {
""",
        """    const double cheap_cost = cost;
    const double frontier_margin
        = std::max(kQualityFrontierAbsMargin,
                   kQualityFrontierRelMargin
                       * std::max(1.0, best_cheap_cost));
    if (net_anchor_samples > 0 && quality_frontier_evals < kQualityFrontierCap
        && cheap_cost <= best_cheap_cost + frontier_margin) {
      ++quality_frontier_evals;
      const double net_anchor_delta = netAnchorDelta(tx, ty);
      if (net_anchor_delta > 0.0) {
        cost += 0.18 * net_anchor_delta;
      } else {
        cost += 0.035 * net_anchor_delta;
      }
    }
    if (cheap_cost < best_cheap_cost) {
      best_cheap_cost = cheap_cost;
    }

    ++prof_candidates_evaluated_;
    if (cost < best_cost) {
""",
    )
    return [str(path)]


def mutate_negotiation_row_bucket_quality_frontier_r5(src: Path) -> list[str]:
    touched: list[str] = []
    touched.extend(mutate_row_bucket_active_set(src))
    touched.extend(mutate_disable_diamond_stall_fallback(src))
    touched.extend(mutate_net_anchor_quality_frontier(src))
    return sorted(set(touched))


def mutate_negotiation_safe_threading(src: Path) -> list[str]:
    """Wire OpenROAD -threads into negotiation and parallelize safe read/update paths.

    This intentionally avoids parallelizing rip-up/place/findBestLocation because
    those paths mutate the placement grid or use the DRC engine.  The cheap wins
    here are deterministic: pass the command-level thread count into the family,
    parallelize row-disjoint history updates, and precompute negotiation sort
    keys in parallel instead of recomputing them inside the comparator.
    """

    touched: list[str] = []

    opendp_h = src / "include" / "dpl_evolve" / "Opendp.h"
    if not opendp_h.is_file():
        raise RuntimeError(f"Missing expected dpl_evolve header: {opendp_h}")
    replace_once(
        opendp_h,
        "  void setDeepIterativePlacement(bool deep_iterative);\n",
        """  void setDeepIterativePlacement(bool deep_iterative);
  void setThreadCount(int thread_count)
  {
    thread_count_ = thread_count > 0 ? thread_count : 1;
  }
""",
    )
    replace_once(
        opendp_h,
        "  bool use_negotiation_ = false;\n",
        """  bool use_negotiation_ = false;
  int thread_count_ = 1;
""",
    )
    touched.append(str(opendp_h))

    opendp_i = variant_file(src, "Opendp.i")
    replace_once(
        opendp_i,
        """  dpl_evolve::Opendp *opendp = ord::OpenRoad::openRoad()->getOpendpEvolve();
  opendp->detailedPlacement(max_displacment_x, max_displacment_y,
""",
        """  dpl_evolve::Opendp *opendp = ord::OpenRoad::openRoad()->getOpendpEvolve();
  opendp->setThreadCount(ord::OpenRoad::openRoad()->getThreadCount());
  opendp->detailedPlacement(max_displacment_x, max_displacment_y,
""",
    )
    touched.append(str(opendp_i))

    opendp_cpp = variant_file(src, "Opendp.cpp")
    replace_once(
        opendp_cpp,
        """    negotiation.setRunAbacus(run_abacus);
    negotiation.legalize();
""",
        """    negotiation.setRunAbacus(run_abacus);
    negotiation.setNumThreads(thread_count_);
    logger_->metric("dpl_evolve__threads", thread_count_);
    negotiation.legalize();
""",
    )
    touched.append(str(opendp_cpp))

    header = variant_file(src, "NegotiationLegalizer.h")
    replace_once(
        header,
        "#include <algorithm>\n",
        "#include <algorithm>\n#include <cstddef>\n",
    )
    replace_once(
        header,
        "  void sortByNegotiationOrder(std::vector<int>& indices) const;\n",
        """  void sortByNegotiationOrder(std::vector<int>& indices) const;
  [[nodiscard]] int workerCountFor(std::size_t work_items,
                                   std::size_t min_items_per_thread = 128) const;
""",
    )
    touched.append(str(header))

    cpp = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_once(
        cpp,
        "#include <string>\n",
        "#include <string>\n#include <thread>\n",
    )
    replace_once(
        cpp,
        """void NegotiationLegalizer::updateHistoryCosts()
{
  for (int gy = 0; gy < grid_h_; ++gy) {
    for (int gx = 0; gx < grid_w_; ++gx) {
      Pixel& g = gridAt(gx, gy);
      const int ov = g.overuse();
      if (ov > 0) {
        g.hist_cost += kHfDefault * ov;
      }
    }
  }
}
""",
        """void NegotiationLegalizer::updateHistoryCosts()
{
  const int workers = workerCountFor(static_cast<std::size_t>(grid_h_), 16);
  logger_->metric("negotiation__parallel__history_threads", workers);

  auto update_rows = [&](int y_begin, int y_end) {
    for (int gy = y_begin; gy < y_end; ++gy) {
      for (int gx = 0; gx < grid_w_; ++gx) {
        Pixel& g = gridAt(gx, gy);
        const int ov = g.overuse();
        if (ov > 0) {
          g.hist_cost += kHfDefault * ov;
        }
      }
    }
  };

  if (workers <= 1) {
    update_rows(0, grid_h_);
    return;
  }

  std::vector<std::thread> pool;
  pool.reserve(workers);
  const int chunk = (grid_h_ + workers - 1) / workers;
  for (int worker = 0; worker < workers; ++worker) {
    const int y_begin = worker * chunk;
    const int y_end = std::min(grid_h_, y_begin + chunk);
    if (y_begin >= y_end) {
      continue;
    }
    pool.emplace_back(update_rows, y_begin, y_end);
  }
  for (auto& thread : pool) {
    thread.join();
  }
}
""",
    )
    replace_once(
        cpp,
        """void NegotiationLegalizer::sortByNegotiationOrder(
    std::vector<int>& indices) const
{
  auto cellOveruse = [this](int idx) {
    const NegCell& cell = cells_[idx];
    int ov = 0;
    const int xBegin = effXBegin(cell);
    const int xEnd = effXEnd(cell);
    for (int dy = 0; dy < cell.height; ++dy) {
      for (int gx = xBegin; gx < xEnd; ++gx) {
        if (gridExists(gx, cell.y + dy)) {
          ov += gridAt(gx, cell.y + dy).overuse();
        }
      }
    }
    return ov;
  };

  std::ranges::sort(indices, [&](int a, int b) {
    const int oa = cellOveruse(a);
    const int ob = cellOveruse(b);
    if (oa != ob) {
      return oa > ob;
    }
    if (cells_[a].height != cells_[b].height) {
      return cells_[a].height < cells_[b].height;
    }
    return cells_[a].width < cells_[b].width;
  });
}
""",
        """void NegotiationLegalizer::sortByNegotiationOrder(
    std::vector<int>& indices) const
{
  struct SortEntry
  {
    int idx = 0;
    int overuse = 0;
  };

  auto cellOveruse = [this](int idx) {
    const NegCell& cell = cells_[idx];
    int ov = 0;
    const int xBegin = effXBegin(cell);
    const int xEnd = effXEnd(cell);
    for (int dy = 0; dy < cell.height; ++dy) {
      for (int gx = xBegin; gx < xEnd; ++gx) {
        if (gridExists(gx, cell.y + dy)) {
          ov += gridAt(gx, cell.y + dy).overuse();
        }
      }
    }
    return ov;
  };

  std::vector<SortEntry> entries(indices.size());
  const int workers = workerCountFor(indices.size(), 256);
  logger_->metric("negotiation__parallel__sort_threads", workers);

  auto fill_entries = [&](std::size_t begin, std::size_t end) {
    for (std::size_t pos = begin; pos < end; ++pos) {
      const int idx = indices[pos];
      entries[pos] = SortEntry{idx, cellOveruse(idx)};
    }
  };

  if (workers <= 1) {
    fill_entries(0, indices.size());
  } else {
    std::vector<std::thread> pool;
    pool.reserve(workers);
    const std::size_t chunk
        = (indices.size() + static_cast<std::size_t>(workers) - 1)
          / static_cast<std::size_t>(workers);
    for (int worker = 0; worker < workers; ++worker) {
      const std::size_t begin = static_cast<std::size_t>(worker) * chunk;
      const std::size_t end = std::min(indices.size(), begin + chunk);
      if (begin >= end) {
        continue;
      }
      pool.emplace_back(fill_entries, begin, end);
    }
    for (auto& thread : pool) {
      thread.join();
    }
  }

  std::ranges::sort(entries, [&](const SortEntry& a, const SortEntry& b) {
    if (a.overuse != b.overuse) {
      return a.overuse > b.overuse;
    }
    if (cells_[a.idx].height != cells_[b.idx].height) {
      return cells_[a.idx].height < cells_[b.idx].height;
    }
    return cells_[a.idx].width < cells_[b.idx].width;
  });

  for (std::size_t pos = 0; pos < entries.size(); ++pos) {
    indices[pos] = entries[pos].idx;
  }
}

int NegotiationLegalizer::workerCountFor(
    const std::size_t work_items,
    const std::size_t min_items_per_thread) const
{
  const int requested = std::max(1, num_threads_);
  if (requested <= 1 || work_items < min_items_per_thread * 2) {
    return 1;
  }
  const std::size_t work_limited
      = std::max<std::size_t>(1, work_items / min_items_per_thread);
  return std::max(1,
                  std::min(requested, static_cast<int>(work_limited)));
}
""",
    )
    touched.append(str(cpp))

    legalizer_cpp = variant_file(src, "NegotiationLegalizer.cpp")
    replace_once(
        legalizer_cpp,
        """  debugPrint(logger_,
             utl::DPL,
             "negotiation",
             1,
             "NegotiationLegalizer: starting legalization.");
""",
        """  num_threads_ = std::max(1, num_threads_);
  logger_->metric("negotiation__parallel__threads_requested", num_threads_);
  logger_->report("NegotiationLegalizer parallel worker budget: {} thread(s).",
                  num_threads_);
  debugPrint(logger_,
             utl::DPL,
             "negotiation",
             1,
             "NegotiationLegalizer: starting legalization with {} thread(s).",
             num_threads_);
""",
    )
    touched.append(str(legalizer_cpp))

    return sorted(set(touched))


def mutate_negotiation_row_bucket_quality_frontier_r5_threaded(src: Path) -> list[str]:
    touched: list[str] = []
    touched.extend(mutate_negotiation_row_bucket_quality_frontier_r5(src))
    touched.extend(mutate_negotiation_safe_threading(src))
    return sorted(set(touched))


def mutate_priority_escape_scale_safe_base(src: Path) -> list[str]:
    touched = mutate_row_bucket_active_set(src)
    touched.extend(mutate_search_narrow_runtime(src))
    return sorted(set(touched))


def mutate_history_strong(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_all(path, "cost += g.hist_cost * penalty;", "cost += 1.15 * g.hist_cost * penalty;")
    return [str(path)]


def mutate_history_soft(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_all(path, "cost += g.hist_cost * penalty;", "cost += 0.85 * g.hist_cost * penalty;")
    return [str(path)]


def mutate_drc_late_ramp(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizerPass.cpp")
    replace_once(
        path,
        "const double kDrcPenalty = 1e3 * (1.0 + iter);",
        "const double kDrcPenalty = 5e2 * (1.0 + 2.0 * iter);",
    )
    return [str(path)]


def mutate_disp_soft(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.h")
    replace_once(path, "constexpr double kMfDefault = 1.5;", "constexpr double kMfDefault = 1.2;")
    replace_once(path, "constexpr int kThDefault = 30;", "constexpr int kThDefault = 40;")
    return [str(path)]


def mutate_disp_strong(src: Path) -> list[str]:
    path = variant_file(src, "NegotiationLegalizer.h")
    replace_once(path, "constexpr double kMfDefault = 1.5;", "constexpr double kMfDefault = 2.0;")
    replace_once(path, "constexpr int kThDefault = 30;", "constexpr int kThDefault = 24;")
    return [str(path)]


TARGET_COST_ORIGINAL = """double NegotiationLegalizer::targetCost(int cell_idx, int x, int y) const
{
  const NegCell& cell = cells_[cell_idx];
  const int disp = std::abs(x - cell.init_x) + std::abs(y - cell.init_y);
  return static_cast<double>(disp)
         + max_disp_multiplier_
               * static_cast<double>(std::max(0, disp - max_disp_threshold_));
}
"""

CONGESTION_COST_ORIGINAL = """      const double penalty = usageWithCell / cap;
      cost += g.hist_cost * penalty;
"""

SORT_ORIGINAL = """  std::ranges::sort(indices, [&](int a, int b) {
    const int oa = cellOveruse(a);
    const int ob = cellOveruse(b);
    if (oa != ob) {
      return oa > ob;
    }
    if (cells_[a].height != cells_[b].height) {
      return cells_[a].height < cells_[b].height;
    }
    return cells_[a].width < cells_[b].width;
  });
"""

POSTOPT_ORIGINAL = """  // greedyImprove(5);
  // cellSwap();
  // greedyImprove(1);
"""

SEARCH_MARKER = """  // Search around the initial (GP) position.
"""

TARGET_COST_MODES: dict[str, str] = {
    "l1_quad_excess": """double NegotiationLegalizer::targetCost(int cell_idx, int x, int y) const
{
  const NegCell& cell = cells_[cell_idx];
  const int dx = std::abs(x - cell.init_x);
  const int dy = std::abs(y - cell.init_y);
  const int disp = dx + dy;
  const int excess = std::max(0, disp - max_disp_threshold_);
  return static_cast<double>(disp)
         + max_disp_multiplier_ * static_cast<double>(excess)
         + 0.035 * static_cast<double>(excess * excess);
}
""",
    "row_guard": """double NegotiationLegalizer::targetCost(int cell_idx, int x, int y) const
{
  const NegCell& cell = cells_[cell_idx];
  const int dx = std::abs(x - cell.init_x);
  const int dy = std::abs(y - cell.init_y);
  const int disp = dx + dy;
  const int excess = std::max(0, disp - max_disp_threshold_);
  const double row_penalty = dy > cell.height ? 0.8 * static_cast<double>(dy) : 0.0;
  return static_cast<double>(disp) + row_penalty
         + max_disp_multiplier_ * static_cast<double>(excess);
}
""",
    "current_blend": """double NegotiationLegalizer::targetCost(int cell_idx, int x, int y) const
{
  const NegCell& cell = cells_[cell_idx];
  const int init_disp = std::abs(x - cell.init_x) + std::abs(y - cell.init_y);
  const int step_disp = std::abs(x - cell.x) + std::abs(y - cell.y);
  const int excess = std::max(0, init_disp - max_disp_threshold_);
  return static_cast<double>(init_disp)
         + 0.20 * static_cast<double>(step_disp)
         + max_disp_multiplier_ * static_cast<double>(excess);
}
""",
    "tall_cell_guard": """double NegotiationLegalizer::targetCost(int cell_idx, int x, int y) const
{
  const NegCell& cell = cells_[cell_idx];
  const int dx = std::abs(x - cell.init_x);
  const int dy = std::abs(y - cell.init_y);
  const int disp = dx + dy;
  const int excess = std::max(0, disp - max_disp_threshold_);
  const double tall_guard = cell.height > 1 ? 0.65 * static_cast<double>(dy * cell.height) : 0.0;
  return static_cast<double>(disp) + tall_guard
         + max_disp_multiplier_ * static_cast<double>(excess);
}
""",
    "width_weighted": """double NegotiationLegalizer::targetCost(int cell_idx, int x, int y) const
{
  const NegCell& cell = cells_[cell_idx];
  const int dx = std::abs(x - cell.init_x);
  const int dy = std::abs(y - cell.init_y);
  const int disp = dx + dy;
  const int excess = std::max(0, disp - max_disp_threshold_);
  const double width_guard = 0.02 * static_cast<double>(cell.width * dx);
  return static_cast<double>(disp) + width_guard
         + max_disp_multiplier_ * static_cast<double>(excess);
}
""",
    "linf_barrier": """double NegotiationLegalizer::targetCost(int cell_idx, int x, int y) const
{
  const NegCell& cell = cells_[cell_idx];
  const int dx = std::abs(x - cell.init_x);
  const int dy = std::abs(y - cell.init_y);
  const int disp = dx + dy;
  const int linf = std::max(dx, dy);
  const int excess = std::max(0, disp - max_disp_threshold_);
  return static_cast<double>(disp)
         + 0.35 * static_cast<double>(linf)
         + max_disp_multiplier_ * static_cast<double>(excess);
}
""",
    "soft_threshold": """double NegotiationLegalizer::targetCost(int cell_idx, int x, int y) const
{
  const NegCell& cell = cells_[cell_idx];
  const int disp = std::abs(x - cell.init_x) + std::abs(y - cell.init_y);
  const int excess = std::max(0, disp - max_disp_threshold_);
  const double soft = std::sqrt(static_cast<double>(1 + std::max(0, disp)));
  return soft + 0.75 * static_cast<double>(disp)
         + max_disp_multiplier_ * static_cast<double>(excess);
}
""",
    "runtime_flat_excess": """double NegotiationLegalizer::targetCost(int cell_idx, int x, int y) const
{
  const NegCell& cell = cells_[cell_idx];
  const int disp = std::abs(x - cell.init_x) + std::abs(y - cell.init_y);
  const int excess = std::max(0, disp - max_disp_threshold_);
  return static_cast<double>(disp)
         + 2.25 * static_cast<double>(excess > 0 ? max_disp_threshold_ + excess : disp);
}
""",
}

CONGESTION_COST_MODES: dict[str, str] = {
    "overflow_square": """      const double penalty = usageWithCell / cap;
      const double overflow = std::max(0.0, usageWithCell - cap);
      cost += g.hist_cost * penalty * penalty + overflow * overflow;
""",
    "history_sqrt": """      const double penalty = usageWithCell / cap;
      cost += std::sqrt(std::max(1.0, g.hist_cost)) * penalty;
""",
    "history_quadratic": """      const double penalty = usageWithCell / cap;
      cost += g.hist_cost * g.hist_cost * penalty;
""",
    "overflow_only": """      const double overflow = std::max(0.0, usageWithCell - cap);
      const double penalty = usageWithCell / cap;
      cost += g.hist_cost * (overflow > 0.0 ? 1.0 + overflow : 0.25 * penalty);
""",
    "capacity_slack": """      const double penalty = usageWithCell / cap;
      const double slack = std::max(0.0, cap - usageWithCell);
      cost += g.hist_cost * penalty - 0.05 * slack;
""",
    "history_capped": """      const double penalty = usageWithCell / cap;
      cost += std::min(g.hist_cost, 12.0) * penalty;
""",
    "multiheight_boost": """      const double penalty = usageWithCell / cap;
      cost += g.hist_cost * penalty * (cell.height > 1 ? 1.35 : 1.0);
""",
    "history_runtime_trim": """      const double penalty = usageWithCell / cap;
      cost += (0.7 * g.hist_cost + 0.3) * penalty;
""",
}

SORT_MODES: dict[str, str] = {
    "overuse_disp_width": """  std::ranges::sort(indices, [&](int a, int b) {
    const int oa = cellOveruse(a);
    const int ob = cellOveruse(b);
    if (oa != ob) {
      return oa > ob;
    }
    if (cells_[a].displacement() != cells_[b].displacement()) {
      return cells_[a].displacement() > cells_[b].displacement();
    }
    return cells_[a].width < cells_[b].width;
  });
""",
    "disp_overuse_small": """  std::ranges::sort(indices, [&](int a, int b) {
    const int da = cells_[a].displacement();
    const int db = cells_[b].displacement();
    if (da != db) {
      return da > db;
    }
    const int oa = cellOveruse(a);
    const int ob = cellOveruse(b);
    if (oa != ob) {
      return oa > ob;
    }
    return cells_[a].width < cells_[b].width;
  });
""",
    "large_first": """  std::ranges::sort(indices, [&](int a, int b) {
    const int area_a = cells_[a].width * cells_[a].height;
    const int area_b = cells_[b].width * cells_[b].height;
    if (area_a != area_b) {
      return area_a > area_b;
    }
    return cellOveruse(a) > cellOveruse(b);
  });
""",
    "tall_first": """  std::ranges::sort(indices, [&](int a, int b) {
    if (cells_[a].height != cells_[b].height) {
      return cells_[a].height > cells_[b].height;
    }
    const int oa = cellOveruse(a);
    const int ob = cellOveruse(b);
    if (oa != ob) {
      return oa > ob;
    }
    return cells_[a].width > cells_[b].width;
  });
""",
    "illegal_first": """  std::ranges::sort(indices, [&](int a, int b) {
    const bool la = isCellLegal(a);
    const bool lb = isCellLegal(b);
    if (la != lb) {
      return !la;
    }
    const int oa = cellOveruse(a);
    const int ob = cellOveruse(b);
    if (oa != ob) {
      return oa > ob;
    }
    return cells_[a].displacement() > cells_[b].displacement();
  });
""",
    "spatial_sweep": """  std::ranges::sort(indices, [&](int a, int b) {
    if (cells_[a].y != cells_[b].y) {
      return cells_[a].y < cells_[b].y;
    }
    if (cells_[a].x != cells_[b].x) {
      return cells_[a].x < cells_[b].x;
    }
    return cellOveruse(a) > cellOveruse(b);
  });
""",
}

SEARCH_MODES: dict[str, str] = {
    "home_probe": """  // Variant candidate probes: always test snapped home/current anchors first.
  const auto snapped_home = snapToLegal(cell_idx, cell.init_x, cell.init_y);
  tryLocation(snapped_home.first, snapped_home.second);
  tryLocation(cell.x, cell.y);

""",
    "sparse_escape": """  // Variant candidate probes: sparse wider escape shell beyond the normal window.
  for (int dy = -2 * adj_window_; dy <= 2 * adj_window_; dy += std::max(1, adj_window_)) {
    for (int dx = -2 * horiz_window_; dx <= 2 * horiz_window_; dx += std::max(1, horiz_window_ / 4)) {
      tryLocation(cell.x + dx, cell.y + dy);
    }
  }

""",
    "vertical_ladder": """  // Variant candidate probes: vertical ladder on the current and initial x anchors.
  for (int dy = -3 * adj_window_; dy <= 3 * adj_window_; dy += std::max(1, cell.height)) {
    tryLocation(cell.init_x, cell.init_y + dy);
    tryLocation(cell.x, cell.y + dy);
  }

""",
    "midpoint_anchor": """  // Variant candidate probes: midpoint between current and global-placement anchors.
  const int mid_x = (cell.x + cell.init_x) / 2;
  const int mid_y = (cell.y + cell.init_y) / 2;
  for (int dy = -adj_window_; dy <= adj_window_; ++dy) {
    for (int dx = -horiz_window_ / 2; dx <= horiz_window_ / 2; ++dx) {
      tryLocation(mid_x + dx, mid_y + dy);
    }
  }

""",
    "cardinal_escape": """  // Variant candidate probes: cardinal escape rays from the current location.
  for (int step = std::max(1, horiz_window_ / 4); step <= 2 * horiz_window_; step += std::max(1, horiz_window_ / 4)) {
    tryLocation(cell.x + step, cell.y);
    tryLocation(cell.x - step, cell.y);
  }
  for (int step = 1; step <= 2 * adj_window_; ++step) {
    tryLocation(cell.x, cell.y + step);
    tryLocation(cell.x, cell.y - step);
  }

""",
    "row_edge_probe": """  // Variant candidate probes: row-edge anchors to escape local horizontal crowding.
  tryLocation(std::max(0, cell.init_x - horiz_window_ - cell.width), cell.init_y);
  tryLocation(std::min(grid_w_ - cell.width, cell.init_x + horiz_window_ + cell.width), cell.init_y);
  tryLocation(std::max(0, cell.x - horiz_window_ - cell.width), cell.y);
  tryLocation(std::min(grid_w_ - cell.width, cell.x + horiz_window_ + cell.width), cell.y);

""",
}

DRC_PENALTY_MODES: dict[str, tuple[str, str]] = {
    "early_lenient": (
        "const double kDrcPenalty = 1e3 * (1.0 + iter);",
        "const double kDrcPenalty = 4e2 * (1.0 + 0.75 * iter);",
    ),
    "quadratic_late": (
        "const double kDrcPenalty = 1e3 * (1.0 + iter);",
        "const double kDrcPenalty = 5e2 * (1.0 + iter + 0.01 * iter * iter);",
    ),
    "flat_strict": (
        "const double kDrcPenalty = 1e3 * (1.0 + iter);",
        "const double kDrcPenalty = 2e4;",
    ),
    "soft_first_50": (
        "const double kDrcPenalty = 1e3 * (1.0 + iter);",
        "const double kDrcPenalty = iter < 50 ? 2e2 : 1e3 * (1.0 + iter);",
    ),
    "disp_aware": (
        "cost += kDrcPenalty * drcCount;",
        "cost += (kDrcPenalty + 10.0 * static_cast<double>(cell.displacement())) * drcCount;",
    ),
}

RECOVERY_MODES: dict[str, tuple[str, str]] = {
    "stall_fast": ("if (stall_count == 3) {", "if (stall_count == 2) {"),
    "stall_patient": ("if (stall_count == 3) {", "if (stall_count == 5) {"),
    "stall_very_patient": ("if (stall_count == 3) {", "if (stall_count == 8) {"),
}

POSTOPT_MODES: dict[str, str] = {
    "none": POSTOPT_ORIGINAL,
    "bounded_local_swap": """  cellSwap();
  syncAllCellsToDplGrid();
""",
    "guarded_swap": """  if (numViolations() == 0) {
    cellSwap();
    syncAllCellsToDplGrid();
  }
""",
    "guarded_greedy": """  if (numViolations() == 0) {
    greedyImprove(1);
    syncAllCellsToDplGrid();
  }
""",
    "guarded_swap_greedy": """  if (numViolations() == 0) {
    cellSwap();
    syncAllCellsToDplGrid();
    if (numViolations() == 0) {
      greedyImprove(1);
      syncAllCellsToDplGrid();
    }
  }
""",
}


def patch_target_cost(mode: str) -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        path = variant_file(src, "NegotiationLegalizerPass.cpp")
        replace_once(path, TARGET_COST_ORIGINAL, TARGET_COST_MODES[mode])
        return [str(path)]

    return apply


def patch_congestion_cost(mode: str) -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        path = variant_file(src, "NegotiationLegalizerPass.cpp")
        replace_once(path, CONGESTION_COST_ORIGINAL, CONGESTION_COST_MODES[mode])
        return [str(path)]

    return apply


def patch_sort_policy(mode: str) -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        path = variant_file(src, "NegotiationLegalizerPass.cpp")
        replace_once(path, SORT_ORIGINAL, SORT_MODES[mode])
        return [str(path)]

    return apply


def patch_search_policy(mode: str) -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        path = variant_file(src, "NegotiationLegalizerPass.cpp")
        replace_once(path, SEARCH_MARKER, SEARCH_MODES[mode] + SEARCH_MARKER)
        return [str(path)]

    return apply


def patch_drc_policy(mode: str) -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        path = variant_file(src, "NegotiationLegalizerPass.cpp")
        old, new = DRC_PENALTY_MODES[mode]
        replace_once(path, old, new)
        return [str(path)]

    return apply


def patch_recovery_policy(mode: str) -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        path = variant_file(src, "NegotiationLegalizerPass.cpp")
        old, new = RECOVERY_MODES[mode]
        replace_all(path, old, new)
        return [str(path)]

    return apply


def patch_postopt(mode: str) -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        if mode == "none":
            return []
        path = variant_file(src, "NegotiationLegalizer.cpp")
        replace_once(path, POSTOPT_ORIGINAL, POSTOPT_MODES[mode])
        return [str(path)]

    return apply


LEGALM_STAGE3_SCORE_ORIGINAL = """      const double current_score
        = (current_hpwl / site_width) + (3.0 * static_cast<double>(current_disp));
"""

LEGALM_STAGE3_BEST_SCORE_ORIGINAL = """      const double best_score
          = (best_hpwl / site_width) + (3.0 * static_cast<double>(best_disp));
"""

LEGALM_REFINE_WINDOW_ORIGINAL = """    const int row_window = cell.pin_count >= 8 ? 4 : 2;
    const int x_window = cell.pin_count >= 8 ? 40 : 20;
    const int max_extra_disp = cell.pin_count >= 8 ? 24 : 12;
"""

LEGALM_STENCIL_XS_ORIGINAL = """    static const std::vector<int> xs = {-40, -20, -10, -5, -4, -3, -2, -1, 0,
                                        1,   2,   3,   4,  5,  10, 20, 40};
"""

LEGALM_STENCIL_YS_ORIGINAL = """    static const std::vector<int> ys = {-6, -5, -4, -3, -2, -1, 0,
                                        1,  2,  3,  4,  5,  6};
"""

LEGALM_ESCAPE_ORIGINAL = """  return stddev(overflow_history_) <= params_.escape_stddev_epsilon
         && totalOverflow() > 0;
"""

LEGALM_LITE_IMPROVE_ORIGINAL = "    improvePlacementLite(1, 40, 6);\n"

LEGALM_STAGE1_ANCHOR_ORIGINAL = """  const Candidate anchor = netAwareAnchorCandidate(cell, context);
  if (lexicographicallyBetter(anchor, best)) {
    best = anchor;
  }
  if (best.valid) {
"""


def patch_legalm_stage1_bounded_recovery() -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        path = variant_file(src, "AlmLegalizer.cpp")
        replace_once(
            path,
            LEGALM_STAGE1_ANCHOR_ORIGINAL,
            """  const Candidate anchor = netAwareAnchorCandidate(cell, context);
  if (lexicographicallyBetter(anchor, best)) {
    best = anchor;
  }
  if (!best.valid) {
    // Stage1 must scale to large designs without full-core scans.  Use bounded
    // expanding windows around the original and net-aware anchors; later
    // Stage2/Stage3 repair handles remaining overflow.
    const std::pair<int, int> kStage1Windows[] = {
        {12, 256}, {24, 512}, {40, 768}, {64, 1024}};
    for (const auto& [row_window, x_window] : kStage1Windows) {
      const Candidate expanded = searchInitialWindowCandidate(
          cell,
          std::min(row_window, core_.height()),
          std::min(x_window, core_.width()));
      if (lexicographicallyBetter(expanded, best)) {
        best = expanded;
      }
      if (best.valid) {
        break;
      }
    }
  }
  if (best.valid) {
""",
        )
        return [str(path)]

    return apply


LEGALM_STAGE2_ALM_SIG = """bool AlmLegalizer::stage2AlmLegalization()"""

LEGALM_STAGE2_ALM_BOUNDED = LEGALM_STAGE2_ALM_SIG + """
{
  initializeAlmParameters();

  const long long core_sites
      = static_cast<long long>(std::max(0, core_.width()))
        * static_cast<long long>(std::max(0, core_.height()));
  const bool large_design = cells_.size() >= 100000 || core_sites >= 2000000LL;
  const int iteration_limit
      = large_design ? std::min(params_.max_iterations, 360) : params_.max_iterations;
  int stagnant_rounds = 0;
  int previous_overflow = std::numeric_limits<int>::max();

  for (int iter = 0; iter < iteration_limit; ++iter) {
    if (iter % params_.k_part == 0 || schemes_.empty()) {
      updatePartitionScheme(iter);
    }

    const bool restart_optimizer = (iter < params_.k_ely) || (iter == params_.k_thre);
    blockGradientDescent(restart_optimizer, false);

    const int overflow = totalOverflow();
    overflow_history_.push_back(overflow);
    while (static_cast<int>(overflow_history_.size()) > params_.escape_window) {
      overflow_history_.pop_front();
    }

    if (overflow == 0) {
      return true;
    }

    if (large_design) {
      if (overflow >= previous_overflow) {
        ++stagnant_rounds;
      } else {
        stagnant_rounds = 0;
      }
      previous_overflow = overflow;
      if (stagnant_rounds >= 80) {
        break;
      }
    }

    updateHfIfNeeded(iter);

    if (params_.enable_escape && detectLocalOptimum()) {
      escapeLocalOptimum();
    }

    updateMultipliers();
  }

  return totalOverflow() == 0;
}
"""

LEGALM_STAGE3_NET_REFINEMENT_SIG = """bool AlmLegalizer::stage3NetRefinement()"""

LEGALM_STAGE3_NET_REFINEMENT_BOUNDED = LEGALM_STAGE3_NET_REFINEMENT_SIG + """
{
  const int site_width = std::max(1, opendp_->grid_->getSiteWidth().v);
  const long long core_sites
      = static_cast<long long>(std::max(0, core_.width()))
        * static_cast<long long>(std::max(0, core_.height()));
  const bool large_design = cells_.size() >= 100000 || core_sites >= 2000000LL;
  const int rank_visit_cap
      = large_design ? 24000 : std::numeric_limits<int>::max();
  const int visit_stride = large_design
                               ? std::max(1,
                                          (static_cast<int>(cells_.size())
                                           + rank_visit_cap - 1)
                                              / rank_visit_cap)
                               : 1;
  const int visit_phase
      = (large_design && visit_stride > 1)
            ? (static_cast<int>(overflow_history_.size()) + 17 * current_scheme_idx_)
                  % visit_stride
            : 0;

  std::vector<int> ranked;
  ranked.reserve(std::min(static_cast<int>(cells_.size()), rank_visit_cap));
  for (int cell_id = visit_phase; cell_id < static_cast<int>(cells_.size());
       cell_id += visit_stride) {
    const CellState& cell = cells_[cell_id];
    const int current_disp = manhattanDisplacement(cell, cell.x, cell.y);
    if (cell.pin_count >= 3 || current_disp >= 8) {
      ranked.push_back(cell_id);
    }
    if (large_design && static_cast<int>(ranked.size()) >= rank_visit_cap) {
      break;
    }
  }

  std::sort(ranked.begin(), ranked.end(), [&](int lhs, int rhs) {
    if (cells_[lhs].pin_count != cells_[rhs].pin_count) {
      return cells_[lhs].pin_count > cells_[rhs].pin_count;
    }
    const int lhs_disp = manhattanDisplacement(cells_[lhs], cells_[lhs].x, cells_[lhs].y);
    const int rhs_disp = manhattanDisplacement(cells_[rhs], cells_[rhs].x, cells_[rhs].y);
    if (lhs_disp != rhs_disp) {
      return lhs_disp > rhs_disp;
    }
    return lhs < rhs;
  });

  const int max_cells = large_design
                            ? std::min(static_cast<int>(ranked.size()), 6000)
                            : std::min(static_cast<int>(ranked.size()),
                                       std::max(1500, static_cast<int>(cells_.size() / 6)));
  for (int i = 0; i < max_cells; ++i) {
    CellState& cell = cells_[ranked[i]];
    removeCellFromGrid(cell);

    const double current_hpwl = localNetHpwlProxy(cell, cell.x, cell.y);
    const int current_disp = manhattanDisplacement(cell, cell.x, cell.y);
    const double current_score
        = (current_hpwl / site_width) + (3.0 * static_cast<double>(current_disp));

    const int row_window = cell.pin_count >= 8 ? 4 : 2;
    const int x_window = cell.pin_count >= 8 ? 40 : 20;
    const int max_extra_disp = cell.pin_count >= 8 ? 24 : 12;
    const Candidate best
        = searchNetRefineCandidate(cell, row_window, x_window, max_extra_disp);

    if (best.valid) {
      const double best_hpwl = localNetHpwlProxy(cell, best.x, best.y);
      const int best_disp = manhattanDisplacement(cell, best.x, best.y);
      const double best_score
          = (best_hpwl / site_width) + (3.0 * static_cast<double>(best_disp));
      if (best_score + 1e-3 < current_score) {
        cell.x = best.x;
        cell.y = best.y;
      }
    }

    addCellToGrid(cell);
  }

  return true;
}
"""

LEGALM_ZERO_OVERFLOW_REPAIR_SIG = """bool AlmLegalizer::zeroOverflowRepair()"""

LEGALM_ZERO_OVERFLOW_REPAIR_BOUNDED = LEGALM_ZERO_OVERFLOW_REPAIR_SIG + """
{
  bool moved_any = false;
  const long long core_sites
      = static_cast<long long>(std::max(0, core_.width()))
        * static_cast<long long>(std::max(0, core_.height()));
  const bool large_design = cells_.size() >= 100000 || core_sites >= 2000000LL;
  const int max_passes = large_design ? 4 : 6;
  const int scan_cap = large_design ? 24000 : std::numeric_limits<int>::max();
  const int repair_cap = large_design ? 6000 : std::numeric_limits<int>::max();
  const int repair_row_window = large_design ? 16 : 24;
  const int repair_x_window = large_design ? 96 : 160;

  for (int pass = 0; pass < max_passes && totalOverflow() > 0; ++pass) {
    const int visit_stride = large_design
                                 ? std::max(1,
                                            (static_cast<int>(cells_.size()) + scan_cap - 1)
                                                / scan_cap)
                                 : 1;
    const int visit_phase
        = (large_design && visit_stride > 1)
              ? (pass * 101 + static_cast<int>(overflow_history_.size()) * 17)
                    % visit_stride
              : 0;

    std::vector<int> ranked;
    ranked.reserve(std::min(static_cast<int>(cells_.size()), scan_cap));
    for (int cell_id = visit_phase; cell_id < static_cast<int>(cells_.size());
         cell_id += visit_stride) {
      if (overflowContribution(cells_[cell_id]) > 0) {
        ranked.push_back(cell_id);
      }
      if (large_design && static_cast<int>(ranked.size()) >= scan_cap) {
        break;
      }
    }
    if (ranked.empty()) {
      break;
    }

    std::sort(ranked.begin(), ranked.end(), [&](int lhs, int rhs) {
      const int lhs_overflow = overflowContribution(cells_[lhs]);
      const int rhs_overflow = overflowContribution(cells_[rhs]);
      if (lhs_overflow != rhs_overflow) {
        return lhs_overflow > rhs_overflow;
      }
      const int lhs_disp = manhattanDisplacement(cells_[lhs], cells_[lhs].x, cells_[lhs].y);
      const int rhs_disp = manhattanDisplacement(cells_[rhs], cells_[rhs].x, cells_[rhs].y);
      if (lhs_disp != rhs_disp) {
        return lhs_disp > rhs_disp;
      }
      return lhs < rhs;
    });

    bool pass_progress = false;
    int repair_attempts = 0;
    for (const int cell_id : ranked) {
      if (repair_attempts >= repair_cap) {
        break;
      }
      ++repair_attempts;
      CellState& cell = cells_[cell_id];
      removeCellFromGrid(cell);
      const Candidate best
          = searchRepairCandidate(cell, repair_row_window, repair_x_window);
      if (best.valid) {
        cell.x = best.x;
        cell.y = best.y;
        pass_progress = true;
        moved_any = true;
      }
      addCellToGrid(cell);
    }

    if (!pass_progress) {
      break;
    }
  }

  return totalOverflow() == 0 || moved_any;
}
"""

LEGALM_SEARCH_INITIAL_WINDOW_SIG = """AlmLegalizer::Candidate AlmLegalizer::searchInitialWindowCandidate(
    const CellState& cell,
    int row_window,
    int x_window) const"""

LEGALM_SEARCH_INITIAL_WINDOW_BOUNDED = LEGALM_SEARCH_INITIAL_WINDOW_SIG + """
{
  Candidate best;
  const int max_y = std::max(core_.ly, core_.uy - cell.h);
  const int max_x = std::max(core_.lx, core_.ux - cell.w);
  const int target_y = clampValue(cell.orig_y, core_.ly, max_y);
  const int target_x = clampValue(cell.orig_x, core_.lx, max_x);

  const bool exact_local_window = row_window <= 8 && x_window <= 160;
  const int candidate_cap = exact_local_window ? 20000 : 8192;
  const int row_slots = 2 * row_window + 1;
  const int x_slots = 2 * x_window + 1;
  const long long nominal_candidates
      = static_cast<long long>(std::max(1, row_slots)) * std::max(1, x_slots);
  const int per_row_budget
      = std::max(8, candidate_cap / std::max(1, row_slots));
  const int x_step = nominal_candidates > candidate_cap
                         ? std::max(1, (x_slots + per_row_budget - 1) / per_row_budget)
                         : 1;
  int tested_candidates = 0;

  auto tryCandidate = [&](int cand_x, int cand_y) {
    if (tested_candidates >= candidate_cap) {
      return;
    }
    if (cand_x < core_.lx || cand_x > max_x || cand_y < core_.ly || cand_y > max_y) {
      return;
    }
    ++tested_candidates;
    const GridRect rect{cand_x, cand_y, cand_x + cell.w, cand_y + cell.h};
    if (!siteRectIsPlaceable(cell, rect)) {
      return;
    }

    Candidate candidate;
    candidate.x = cand_x;
    candidate.y = cand_y;
    candidate.cost = static_cast<double>(
        manhattanDisplacement(cell, candidate.x, candidate.y));
    candidate.valid = true;
    if (lexicographicallyBetter(candidate, best)) {
      best = candidate;
    }
  };

  for (int row_delta = 0; row_delta <= row_window; ++row_delta) {
    for (int row_sign : {0, -1, 1}) {
      if ((row_sign == 0) != (row_delta == 0)) {
        continue;
      }
      const int cand_y = target_y + row_sign * row_delta * cell.vertical_step;
      if (cand_y < core_.ly || cand_y > max_y || !satisfiesRailAlignment(cell, cand_y)) {
        continue;
      }

      tryCandidate(target_x, cand_y);
      for (int x_delta = x_step; x_delta <= x_window; x_delta += x_step) {
        tryCandidate(target_x - x_delta, cand_y);
        tryCandidate(target_x + x_delta, cand_y);
      }
      if (x_window > 0 && (x_window % x_step) != 0) {
        tryCandidate(target_x - x_window, cand_y);
        tryCandidate(target_x + x_window, cand_y);
      }
      if (tested_candidates >= candidate_cap) {
        return best;
      }
    }
  }

  return best;
}
"""

LEGALM_BLOCK_GRADIENT_SIG = """int AlmLegalizer::blockGradientDescent(bool restart_optimizer,
                                       bool forbid_overflow)"""

LEGALM_BLOCK_GRADIENT_BOUNDED = LEGALM_BLOCK_GRADIENT_SIG + """
{
  if (schemes_.empty()) {
    return 0;
  }

  int moved_cells = 0;
  int visited_cells = 0;
  auto& scheme = schemes_[current_scheme_idx_];
  const long long core_sites
      = static_cast<long long>(std::max(0, core_.width()))
        * static_cast<long long>(std::max(0, core_.height()));
  const bool large_design = cells_.size() >= 100000 || core_sites >= 2000000LL;
  const int global_visit_cap
      = large_design ? (forbid_overflow ? 12000 : 24000)
                     : std::numeric_limits<int>::max();
  const int part_visit_cap
      = large_design ? (forbid_overflow ? 192 : 384)
                     : std::numeric_limits<int>::max();
  const int visit_epoch = static_cast<int>(overflow_history_.size())
                          + 17 * current_scheme_idx_
                          + (restart_optimizer ? 31 : 0)
                          + (forbid_overflow ? 47 : 0);

  for (Partition& part : scheme.parts) {
    const int part_size = static_cast<int>(part.cell_ids.size());
    if (part_size == 0) {
      continue;
    }
    const int visit_stride = large_design
                                 ? std::max(1, (part_size + part_visit_cap - 1)
                                                   / part_visit_cap)
                                 : 1;
    const int visit_phase
        = (large_design && visit_stride > 1) ? visit_epoch % visit_stride : 0;

    std::vector<int> ranked;
    ranked.reserve(std::min(part_size, part_visit_cap));
    for (int pos = visit_phase; pos < part_size; pos += visit_stride) {
      const int cell_id = part.cell_ids[pos];
      CellState& cell = cells_[cell_id];
      cell.last_demand = cellDemand(cell);
      if (large_design && !restart_optimizer && !forbid_overflow
          && cell.last_demand <= 0.0 && cell.pin_count < 8) {
        continue;
      }
      ranked.push_back(cell_id);
      if (large_design && static_cast<int>(ranked.size()) >= part_visit_cap) {
        break;
      }
    }
    if (ranked.empty()) {
      continue;
    }

    std::sort(ranked.begin(), ranked.end(), [&](int lhs, int rhs) {
      const double lhs_demand = cells_[lhs].last_demand;
      const double rhs_demand = cells_[rhs].last_demand;
      if (lhs_demand != rhs_demand) {
        return lhs_demand > rhs_demand;
      }
      if (cells_[lhs].pin_count != cells_[rhs].pin_count) {
        return cells_[lhs].pin_count > cells_[rhs].pin_count;
      }
      const int lhs_disp = manhattanDisplacement(cells_[lhs], cells_[lhs].x, cells_[lhs].y);
      const int rhs_disp = manhattanDisplacement(cells_[rhs], cells_[rhs].x, cells_[rhs].y);
      if (lhs_disp != rhs_disp) {
        return lhs_disp > rhs_disp;
      }
      return lhs < rhs;
    });

    for (const int cell_id : ranked) {
      if (visited_cells >= global_visit_cap) {
        return moved_cells;
      }
      ++visited_cells;
      const Candidate best
          = gradientDescentSingleCell(cell_id, part, restart_optimizer, forbid_overflow);
      if (best.valid) {
        CellState& cell = cells_[cell_id];
        if (cell.x != best.x || cell.y != best.y) {
          ++moved_cells;
        }
        moveCell(cell, best.x, best.y);
      }
    }
  }

  return moved_cells;
}
"""

LEGALM_TOTAL_OVERFLOW_SIG = """int AlmLegalizer::totalOverflow() const"""

LEGALM_TOTAL_OVERFLOW_COUNTER = LEGALM_TOTAL_OVERFLOW_SIG + """
{
  return total_overflow_;
}
"""

LEGALM_UPDATE_MULTIPLIERS_SIG = """void AlmLegalizer::updateMultipliers()"""

LEGALM_UPDATE_MULTIPLIERS_BOUNDED = LEGALM_UPDATE_MULTIPLIERS_SIG + """
{
  const int width = std::max(0, core_.width());
  const int height = std::max(0, core_.height());
  if (width == 0 || height == 0) {
    return;
  }

  const long long core_sites
      = static_cast<long long>(width) * static_cast<long long>(height);
  const bool large_core = core_sites >= 2000000LL;
  const int visit_cap
      = large_core ? 250000
                   : static_cast<int>(
                         std::min<long long>(core_sites,
                                             std::numeric_limits<int>::max()));
  const long long stride
      = large_core ? std::max(1LL,
                              (core_sites + static_cast<long long>(visit_cap) - 1LL)
                                  / static_cast<long long>(visit_cap))
                   : 1LL;
  const long long phase
      = (large_core && stride > 1)
            ? (static_cast<long long>(overflow_history_.size()) * 9973LL) % stride
            : 0LL;

  for (long long linear = phase; linear < core_sites; linear += stride) {
    const int x = core_.lx + static_cast<int>(linear % width);
    const int y = core_.ly + static_cast<int>(linear / width);
    const int idx = grid_.index(x, y);
    const double gj = static_cast<double>(overflowAtSite(x, y));
    const double g_tilde = std::max(gj, -1.0 / sigma_);
    const double delta = hf_ * (g_tilde + (sigma_ / 2.0) * g_tilde * g_tilde);
    grid_.lambda[idx] = std::max(grid_.lambda[idx] + delta, 0.0);
  }
}
"""


def patch_legalm_bounded_engine_complexity() -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        path = variant_file(src, "AlmLegalizer.cpp")
        replacements = (
            (LEGALM_STAGE2_ALM_SIG, LEGALM_STAGE2_ALM_BOUNDED),
            (LEGALM_STAGE3_NET_REFINEMENT_SIG, LEGALM_STAGE3_NET_REFINEMENT_BOUNDED),
            (LEGALM_ZERO_OVERFLOW_REPAIR_SIG, LEGALM_ZERO_OVERFLOW_REPAIR_BOUNDED),
            (LEGALM_SEARCH_INITIAL_WINDOW_SIG, LEGALM_SEARCH_INITIAL_WINDOW_BOUNDED),
            (LEGALM_BLOCK_GRADIENT_SIG, LEGALM_BLOCK_GRADIENT_BOUNDED),
            (LEGALM_TOTAL_OVERFLOW_SIG, LEGALM_TOTAL_OVERFLOW_COUNTER),
            (LEGALM_UPDATE_MULTIPLIERS_SIG, LEGALM_UPDATE_MULTIPLIERS_BOUNDED),
        )
        for signature, replacement in replacements:
            replace_cpp_function(path, signature, replacement)
        return [str(path)]

    return apply


def patch_legalm_stage3_score(mode: str) -> Callable[[Path], list[str]]:
    weights = {
        "hpwl_heavy": "2.0",
        "disp_guard": "4.5",
        "balanced": "3.5",
        "aggressive_hpwl": "1.5",
    }

    def apply(src: Path) -> list[str]:
        weight = weights[mode]
        path = variant_file(src, "AlmLegalizer.cpp")
        replace_once(
            path,
            "(3.0 * static_cast<double>(current_disp))",
            f"({weight} * static_cast<double>(current_disp))",
        )
        replace_once(
            path,
            "(3.0 * static_cast<double>(best_disp))",
            f"({weight} * static_cast<double>(best_disp))",
        )
        return [str(path)]

    return apply


def patch_legalm_refine_window(mode: str) -> Callable[[Path], list[str]]:
    windows = {
        "pinwide": """    const int row_window = cell.pin_count >= 8 ? 5 : 3;
    const int x_window = cell.pin_count >= 8 ? 56 : 28;
    const int max_extra_disp = cell.pin_count >= 8 ? 32 : 16;
""",
        "tight": """    const int row_window = cell.pin_count >= 8 ? 3 : 1;
    const int x_window = cell.pin_count >= 8 ? 28 : 14;
    const int max_extra_disp = cell.pin_count >= 8 ? 18 : 9;
""",
        "all_balanced": """    const int row_window = cell.pin_count >= 8 ? 4 : 3;
    const int x_window = cell.pin_count >= 8 ? 44 : 26;
    const int max_extra_disp = cell.pin_count >= 8 ? 24 : 16;
""",
        "highpin_only": """    const int row_window = cell.pin_count >= 12 ? 6 : 2;
    const int x_window = cell.pin_count >= 12 ? 64 : 20;
    const int max_extra_disp = cell.pin_count >= 12 ? 36 : 12;
""",
    }

    def apply(src: Path) -> list[str]:
        path = variant_file(src, "AlmLegalizer.cpp")
        replace_once(path, LEGALM_REFINE_WINDOW_ORIGINAL, windows[mode])
        return [str(path)]

    return apply


def patch_legalm_stencil(mode: str) -> Callable[[Path], list[str]]:
    xs = {
        "local_dense": """    static const std::vector<int> xs = {-24, -16, -10, -6, -4, -3, -2, -1, 0,
                                        1,   2,   3,   4,  6,  10, 16, 24};
""",
        "long_escape": """    static const std::vector<int> xs = {-64, -40, -24, -12, -6, -3, -1, 0,
                                        1,   3,   6,   12, 24, 40, 64};
""",
        "medium_ring": """    static const std::vector<int> xs = {-48, -32, -20, -12, -8, -4, -2, -1, 0,
                                        1,   2,   4,   8,  12, 20, 32, 48};
""",
    }
    ys = {
        "local_dense": """    static const std::vector<int> ys = {-4, -3, -2, -1, 0,
                                        1,  2,  3,  4};
""",
        "long_escape": """    static const std::vector<int> ys = {-8, -6, -4, -2, -1, 0,
                                        1,  2,  4,  6,  8};
""",
        "medium_ring": """    static const std::vector<int> ys = {-7, -5, -3, -2, -1, 0,
                                        1,  2,  3,  5,  7};
""",
    }

    def apply(src: Path) -> list[str]:
        path = variant_file(src, "AlmLegalizer.cpp")
        replace_once(path, LEGALM_STENCIL_XS_ORIGINAL, xs[mode])
        replace_once(path, LEGALM_STENCIL_YS_ORIGINAL, ys[mode])
        return [str(path)]

    return apply


def patch_legalm_escape(mode: str) -> Callable[[Path], list[str]]:
    replacements = {
        "eager": """  return stddev(overflow_history_) <= 2.0 * params_.escape_stddev_epsilon
         && totalOverflow() > 0;
""",
        "strict": """  return stddev(overflow_history_) <= 0.5 * params_.escape_stddev_epsilon
         && totalOverflow() > 0;
""",
        "plateau_or_worse": """  return totalOverflow() > 0
         && (stddev(overflow_history_) <= params_.escape_stddev_epsilon
             || overflow_history_.back() >= overflow_history_.front());
""",
    }

    def apply(src: Path) -> list[str]:
        path = variant_file(src, "AlmLegalizer.cpp")
        replace_once(path, LEGALM_ESCAPE_ORIGINAL, replacements[mode])
        return [str(path)]

    return apply


def patch_legalm_lite_improve(mode: str) -> Callable[[Path], list[str]]:
    replacements = {
        "skip": "",
        "tight": "    improvePlacementLite(1, 24, 4);\n",
        "wide": "    improvePlacementLite(1, 56, 8);\n",
        "double_tight": "    improvePlacementLite(2, 24, 4);\n",
    }

    def apply(src: Path) -> list[str]:
        path = variant_file(src, "Opendp.cpp")
        replace_once(path, LEGALM_LITE_IMPROVE_ORIGINAL, replacements[mode])
        return [str(path)]

    return apply


def compose_variant_apply(changes: tuple[Callable[[Path], list[str]], ...]) -> Callable[[Path], list[str]]:
    def apply(src: Path) -> list[str]:
        touched: list[str] = []
        for change in changes:
            touched.extend(change(src))
        return sorted(set(touched))

    return apply


def short_mode_name(mode: str) -> str:
    return "".join(part[:3] for part in mode.split("_"))[:10]


def build_algorithmic_variants(count: int = 60) -> dict[str, VariantSpec]:
    target_modes = list(TARGET_COST_MODES)
    congestion_modes = list(CONGESTION_COST_MODES)
    sort_modes = list(SORT_MODES)
    search_modes = list(SEARCH_MODES)
    drc_modes = list(DRC_PENALTY_MODES)
    recovery_modes = ["none", *RECOVERY_MODES.keys()]
    post_modes = list(POSTOPT_MODES)
    variants: dict[str, VariantSpec] = {}

    for i in range(count):
        target = target_modes[i % len(target_modes)]
        congestion = congestion_modes[(i * 3 + 1) % len(congestion_modes)]
        sort = sort_modes[(i * 5 + 2) % len(sort_modes)]
        search = search_modes[(i * 7 + 3) % len(search_modes)]
        drc = drc_modes[(i * 11 + 4) % len(drc_modes)]
        recovery = recovery_modes[(i * 13 + 5) % len(recovery_modes)]
        post = post_modes[(i * 17 + 6) % len(post_modes)]

        changes: list[Callable[[Path], list[str]]] = [
            patch_target_cost(target),
            patch_congestion_cost(congestion),
            patch_sort_policy(sort),
            patch_search_policy(search),
            patch_drc_policy(drc),
        ]
        if recovery != "none":
            changes.append(patch_recovery_policy(recovery))
        if post != "none":
            changes.append(patch_postopt(post))

        name = (
            f"alg{i + 1:02d}_"
            f"{short_mode_name(target)}_"
            f"{short_mode_name(congestion)}_"
            f"{short_mode_name(search)}"
        )
        variants[name] = VariantSpec(
            name=name,
            family="algorithmic_composite",
            touched_symbol=(
                "NegotiationLegalizer::targetCost+negotiationCost+"
                "findBestLocation+sortByNegotiationOrder"
            ),
            summary=(
                f"Composite algorithmic variant: target={target}, "
                f"congestion={congestion}, sort={sort}, search={search}, "
                f"drc={drc}, recovery={recovery}, postopt={post}."
            ),
            apply=compose_variant_apply(tuple(changes)),
            algorithmic_changes=(
                f"target_cost:{target}",
                f"congestion_cost:{congestion}",
                f"sort_policy:{sort}",
                f"search_policy:{search}",
                f"drc_policy:{drc}",
                f"recovery_policy:{recovery}",
                f"postopt_policy:{post}",
            ),
        )

    return variants


def build_netaware_family_variants() -> dict[str, VariantSpec]:
    recipes = [
        ("netaware01_hpwl_endpoint_guard", "l1_quad_excess", "overflow_square", "overuse_disp_width", "home_probe"),
        ("netaware02_history_sqrt_anchor", "current_blend", "history_sqrt", "disp_overuse_small", "midpoint_anchor"),
        ("netaware03_row_guard_frontier", "row_guard", "capacity_slack", "illegal_first", "row_edge_probe"),
        ("netaware04_width_endpoint", "width_weighted", "overflow_only", "overuse_disp_width", "cardinal_escape"),
        ("netaware05_linf_sparse", "linf_barrier", "history_capped", "large_first", "sparse_escape"),
        ("netaware06_soft_threshold_ladder", "soft_threshold", "history_runtime_trim", "spatial_sweep", "vertical_ladder"),
        ("netaware07_tall_multiheight", "tall_cell_guard", "multiheight_boost", "tall_first", "home_probe"),
        ("netaware08_runtime_flat_slack", "runtime_flat_excess", "capacity_slack", "disp_overuse_small", "row_edge_probe"),
        ("netaware09_quad_overflow_beam", "l1_quad_excess", "history_quadratic", "illegal_first", "midpoint_anchor"),
        ("netaware10_blend_overflow_only", "current_blend", "overflow_only", "spatial_sweep", "cardinal_escape"),
    ]
    variants: dict[str, VariantSpec] = {}
    for name, target, congestion, sort, search in recipes:
        changes = (
            patch_target_cost(target),
            patch_congestion_cost(congestion),
            patch_sort_policy(sort),
            patch_search_policy(search),
        )
        variants[name] = VariantSpec(
            name=name,
            family="netaware_objective",
            touched_symbol=(
                "NegotiationLegalizer::targetCost+negotiationCost+"
                "findBestLocation+sortByNegotiationOrder"
            ),
            summary=(
                "Net-aware objective/search family variant using "
                f"target={target}, congestion={congestion}, sort={sort}, search={search}."
            ),
            apply=compose_variant_apply(changes),
            algorithmic_changes=(
                f"target_cost:{target}",
                f"congestion_cost:{congestion}",
                f"sort_policy:{sort}",
                f"search_policy:{search}",
            ),
            source_family="clean_evolve_base",
            startpoint="clean_or_runtime_aware_negotiation",
        )
    return variants


def build_localized_swap_family_variants() -> dict[str, VariantSpec]:
    recipes = [
        ("localswap01_bounded_local_polish", "bounded_local_swap"),
    ]
    variants: dict[str, VariantSpec] = {}
    for name, post in recipes:
        changes = (patch_postopt(post),)
        variants[name] = VariantSpec(
            name=name,
            family="localized_swap",
            touched_symbol="NegotiationLegalizer::legalize+cellSwap",
            summary=(
                "Compressed localized/postopt polish variant.  It enables the "
                "bounded local swap primitive only: hotset seeds, spatial "
                "bucket/window candidates, accepted-move/candidate/time caps, "
                "and transactional legality rollback.  It must not use a "
                "fallback or the old full-pair swap path on large cases."
            ),
            apply=compose_variant_apply(changes),
            algorithmic_changes=(f"postopt_policy:{post}",),
            source_family="clean_evolve_base",
            startpoint="compressed_postlegalization_polish_only",
        )
    return variants


def build_priority_escape_family_variants() -> dict[str, VariantSpec]:
    recipes = [
        ("priority01_home_stall_fast", "home_probe", "stall_fast", "early_lenient", "illegal_first"),
        ("priority02_sparse_patient", "sparse_escape", "stall_patient", "quadratic_late", "overuse_disp_width"),
        ("priority03_ladder_drc", "vertical_ladder", "stall_fast", "disp_aware", "disp_overuse_small"),
        ("priority04_midpoint_soft50", "midpoint_anchor", "stall_very_patient", "soft_first_50", "large_first"),
        ("priority05_cardinal_strict", "cardinal_escape", "stall_patient", "flat_strict", "illegal_first"),
        ("priority06_rowedge_fast", "row_edge_probe", "stall_fast", "early_lenient", "spatial_sweep"),
        ("priority07_sparse_disp", "sparse_escape", "stall_very_patient", "disp_aware", "tall_first"),
        ("priority08_midpoint_quad", "midpoint_anchor", "stall_patient", "quadratic_late", "overuse_disp_width"),
        ("priority09_ladder_soft50", "vertical_ladder", "stall_fast", "soft_first_50", "illegal_first"),
        ("priority10_cardinal_patient", "cardinal_escape", "stall_very_patient", "early_lenient", "disp_overuse_small"),
    ]
    variants: dict[str, VariantSpec] = {}
    for name, search, recovery, drc, sort in recipes:
        changes = (
            patch_search_policy(search),
            patch_recovery_policy(recovery),
            patch_drc_policy(drc),
            patch_sort_policy(sort),
        )
        variants[name] = VariantSpec(
            name=name,
            family="priority_escape",
            touched_symbol=(
                "NegotiationLegalizer::findBestLocation+negotiationIter+"
                "sortByNegotiationOrder"
            ),
            summary=(
                "Priority/stuck-cell escape variant using "
                f"search={search}, recovery={recovery}, drc={drc}, sort={sort}."
            ),
            apply=compose_variant_apply(changes),
            algorithmic_changes=(
                f"search_policy:{search}",
                f"recovery_policy:{recovery}",
                f"drc_policy:{drc}",
                f"sort_policy:{sort}",
            ),
            source_family="clean_evolve_base",
            startpoint="priority_escape",
        )
    return variants


def build_legalm_family_variants() -> dict[str, VariantSpec]:
    recipes = [
        ("legalm01_hpwl_pinwide", "hpwl_heavy", "pinwide", "medium_ring", "eager"),
        ("legalm02_disp_tight", "disp_guard", "tight", "local_dense", "strict"),
        ("legalm03_balanced_wide", "balanced", "all_balanced", "long_escape", "eager"),
        ("legalm04_aggressive_guard", "aggressive_hpwl", "pinwide", "medium_ring", "plateau_or_worse"),
        ("legalm05_highpin_wide", "hpwl_heavy", "highpin_only", "long_escape", "eager"),
        ("legalm06_strict_local", "disp_guard", "all_balanced", "local_dense", "strict"),
        ("legalm07_medium_escape", "balanced", "tight", "medium_ring", "plateau_or_worse"),
        ("legalm08_hpwl_local", "aggressive_hpwl", "all_balanced", "local_dense", "eager"),
        ("legalm09_guarded_long", "disp_guard", "highpin_only", "long_escape", "plateau_or_worse"),
        ("legalm10_balanced_local", "balanced", "pinwide", "local_dense", "strict"),
    ]
    variants: dict[str, VariantSpec] = {}
    for name, score, window, stencil, escape in recipes:
        changes = (
            patch_legalm_stage1_bounded_recovery(),
            patch_legalm_bounded_engine_complexity(),
            patch_legalm_stage3_score(score),
            patch_legalm_refine_window(window),
            patch_legalm_stencil(stencil),
            patch_legalm_escape(escape),
            patch_legalm_lite_improve("skip"),
        )
        variants[name] = VariantSpec(
            name=name,
            family="legalm_engine",
            touched_symbol=(
                "AlmLegalizer::stage1InitialLegalization+stage2AlmLegalization+"
                "stage3NetRefinement+zeroOverflowRepair+Opendp::detailedPlacement"
            ),
            summary=(
                "LEGALM materialized-family variant evaluated through the same "
                f"evolve entrypoint using score={score}, window={window}, "
                f"stencil={stencil}, escape={escape}, bounded hotsets, and "
                "no default/diamond fallback."
            ),
            apply=compose_variant_apply(changes),
            algorithmic_changes=(
                "legalm_stage1_recovery:bounded_expanding_windows",
                "legalm_complexity:bounded_stage1_stage2_stage3_hotsets",
                "legalm_total_overflow:maintained_counter_no_core_scan",
                "legalm_multiplier_update:bounded_rotating_core_sample",
                f"legalm_stage3_score:{score}",
                f"legalm_refine_window:{window}",
                f"legalm_stencil:{stencil}",
                f"legalm_escape:{escape}",
                "legalm_default_polish:disabled",
            ),
            source_family="legalm_engine",
            startpoint="materialized_legalm_engine_same_evolve_entrypoint",
        )
    return variants


VARIANTS: dict[str, VariantSpec] = {
    "greedy1": VariantSpec(
        name="greedy1",
        family="localized_postopt",
        touched_symbol="NegotiationLegalizer::legalize",
        summary="Enable one greedyImprove pass after the main negotiation legalizer.",
        apply=mutate_greedy1,
    ),
    "greedy2": VariantSpec(
        name="greedy2",
        family="localized_postopt",
        touched_symbol="NegotiationLegalizer::legalize",
        summary="Enable two greedyImprove passes after the main negotiation legalizer.",
        apply=mutate_greedy2,
    ),
    "search_narrow_runtime": VariantSpec(
        name="search_narrow_runtime",
        family="search_window_tuning",
        touched_symbol="NegotiationLegalizer::findBestLocation",
        summary="Shrink horizontal and adjacent row windows to test runtime-sensitive cases.",
        apply=mutate_search_narrow_runtime,
    ),
    "search_wide_escape": VariantSpec(
        name="search_wide_escape",
        family="search_window_tuning",
        touched_symbol="NegotiationLegalizer::findBestLocation",
        summary="Widen horizontal and adjacent row windows to test stuck-cell escape.",
        apply=mutate_search_wide_escape,
    ),
    "large_design_diamond_fallback": VariantSpec(
        name="large_design_diamond_fallback",
        family="runtime_safe_fallback",
        touched_symbol="Opendp::detailedPlacement",
        summary=(
            "Keep the same detailed_placement_evolve -use_negotiation entrypoint "
            "but route very large designs to the fast diamond legalizer internally. "
            "Diagnostic safety fuse only; not a robust-base algorithm."
        ),
        apply=mutate_large_design_diamond_fallback,
        algorithmic_changes=("large_design_runtime_fallback:diamond_dpl",),
    ),
    "negotiation_row_bucket_active_set": VariantSpec(
        name="negotiation_row_bucket_active_set",
        family="netaware_runtime_active_set",
        touched_symbol="NegotiationLegalizer::runNegotiation",
        summary=(
            "Replace illegal-seed x all-cell active-set expansion with a "
            "row-bucket spatial index, bounded neighborhood scan, dirty-region "
            "bystander repair, and large-design candidate caps."
        ),
        apply=mutate_row_bucket_active_set,
        algorithmic_changes=(
            "active_set_initialization:row_bucket_spatial_index",
            "bounded_neighbor_expansion:seed_window_rows",
            "bystander_repair:dirty_region_row_bucket_scan",
            "active_frontier:per_seed_candidate_cap",
            "candidate_generation:large_design_horizontal_stride_cap",
            "candidate_generation:per_cell_candidate_budget",
        ),
        source_family="clean_evolve_base",
        startpoint="clean_or_runtime_aware_negotiation",
    ),
    "negotiation_row_bucket_quality_frontier_r5": VariantSpec(
        name="negotiation_row_bucket_quality_frontier_r5",
        family="negotiation_row_bucket",
        touched_symbol=(
            "NegotiationLegalizer::runNegotiation+findBestLocation"
        ),
        summary=(
            "Flow-usable row-bucket quality-frontier candidate. It keeps the "
            "scale-safe row-bucket active set, disables diamond stall fallback "
            "as family evidence, and applies net-anchor quality scoring only "
            "to a bounded cheap-score frontier."
        ),
        apply=mutate_negotiation_row_bucket_quality_frontier_r5,
        algorithmic_changes=(
            "active_set_initialization:row_bucket_spatial_index",
            "bystander_repair:dirty_region_row_bucket_scan",
            "large_design_find_best:candidate_cap_with_anchor_probes",
            "stall_policy:no_diamond_fallback_as_success",
            "quality_proxy:net_anchor_delta_on_bounded_frontier",
            "displacement_guard:quadratic_outlier_excess",
        ),
        source_family="clean_evolve_base",
        startpoint="negotiation_row_bucket_active_set+quality_frontier_r5",
    ),
    "negotiation_row_bucket_quality_frontier_r5_threaded": VariantSpec(
        name="negotiation_row_bucket_quality_frontier_r5_threaded",
        family="negotiation_row_bucket",
        touched_symbol=(
            "Opendp::detailedPlacement+NegotiationLegalizer::updateHistoryCosts+"
            "sortByNegotiationOrder"
        ),
        summary=(
            "R5 row-bucket quality-frontier family with OpenROAD -threads wired "
            "into the negotiation legalizer and safe parallelism for row-disjoint "
            "history updates plus precomputed sort keys.  It deliberately keeps "
            "rip-up/place/findBest serial because those paths mutate the grid."
        ),
        apply=mutate_negotiation_row_bucket_quality_frontier_r5_threaded,
        algorithmic_changes=(
            "active_set_initialization:row_bucket_spatial_index",
            "bystander_repair:dirty_region_row_bucket_scan",
            "quality_proxy:net_anchor_delta_on_bounded_frontier",
            "threading:openroad_thread_count_to_negotiation",
            "threading:parallel_history_cost_by_row",
            "threading:parallel_sort_key_precompute",
        ),
        source_family="clean_evolve_base",
        startpoint="negotiation_row_bucket_quality_frontier_r5+safe_threading",
    ),
    "priority_escape_scale_safe_base": VariantSpec(
        name="priority_escape_scale_safe_base",
        family="priority_escape",
        touched_symbol=(
            "NegotiationLegalizer::runNegotiation+negotiationIter+"
            "findBestLocation"
        ),
        summary=(
            "Priority/negotiation base candidate built from the scale-safe "
            "row-bucket active set, dirty-region bystander scan, bounded "
            "frontier expansion, and capped large-design candidate budgets. "
            "This keeps the common detailed_placement_evolve -use_negotiation "
            "entrypoint and does not route large cases to a fallback legalizer."
        ),
        apply=mutate_priority_escape_scale_safe_base,
        algorithmic_changes=(
            "active_set_initialization:row_bucket_spatial_index",
            "bystander_repair:dirty_region_row_bucket_scan",
            "active_frontier:per_seed_candidate_cap",
            "candidate_generation:large_design_horizontal_stride_cap",
            "candidate_generation:per_cell_candidate_budget",
            "search_window:runtime_safe_narrow_base",
        ),
        source_family="clean_evolve_base",
        startpoint="scale_safe_priority_negotiation_base",
    ),
    "history_strong": VariantSpec(
        name="history_strong",
        family="objective_cost_shaping",
        touched_symbol="NegotiationLegalizer::negotiationCost",
        summary="Increase historical congestion pressure in the negotiation objective.",
        apply=mutate_history_strong,
    ),
    "history_soft": VariantSpec(
        name="history_soft",
        family="objective_cost_shaping",
        touched_symbol="NegotiationLegalizer::negotiationCost",
        summary="Soften historical congestion pressure in the negotiation objective.",
        apply=mutate_history_soft,
    ),
    "drc_late_ramp": VariantSpec(
        name="drc_late_ramp",
        family="candidate_generation",
        touched_symbol="NegotiationLegalizer::findBestLocation",
        summary="Reduce early DRC penalty but ramp it more strongly over iterations.",
        apply=mutate_drc_late_ramp,
    ),
    "disp_soft": VariantSpec(
        name="disp_soft",
        family="objective_cost_shaping",
        touched_symbol="targetCost",
        summary="Relax max-displacement pressure to test HPWL headroom.",
        apply=mutate_disp_soft,
    ),
    "disp_strong": VariantSpec(
        name="disp_strong",
        family="objective_cost_shaping",
        touched_symbol="targetCost",
        summary="Increase max-displacement pressure to test conservative legalization.",
        apply=mutate_disp_strong,
    ),
}

ALGORITHMIC_VARIANTS = build_algorithmic_variants(60)
VARIANTS.update(ALGORITHMIC_VARIANTS)
NETAWARE_VARIANTS = build_netaware_family_variants()
LOCALIZED_SWAP_VARIANTS = build_localized_swap_family_variants()
PRIORITY_ESCAPE_VARIANTS = build_priority_escape_family_variants()
LEGALM_VARIANTS = build_legalm_family_variants()
VARIANTS.update(NETAWARE_VARIANTS)
VARIANTS.update(LOCALIZED_SWAP_VARIANTS)
VARIANTS.update(PRIORITY_ESCAPE_VARIANTS)
VARIANTS.update(LEGALM_VARIANTS)
VARIANTS["legalm_base_bounded_stage1"] = VariantSpec(
    name="legalm_base_bounded_stage1",
    family="legalm_engine",
    touched_symbol=(
        "AlmLegalizer::findNearestInitialCandidate+stage2AlmLegalization+"
        "blockGradientDescent+zeroOverflowRepair+stage3NetRefinement"
    ),
    summary=(
        "LEGALM base-family candidate using bounded Stage1 expanding windows, "
        "bounded Stage2/Stage3 hotsets, conservative displacement scoring, "
        "local stencil repair, no default/diamond fallback, and the same "
        "detailed_placement_evolve -use_negotiation entrypoint."
    ),
    apply=compose_variant_apply(
        (
            patch_legalm_stage1_bounded_recovery(),
            patch_legalm_bounded_engine_complexity(),
            patch_legalm_stage3_score("disp_guard"),
            patch_legalm_refine_window("tight"),
            patch_legalm_stencil("local_dense"),
            patch_legalm_escape("strict"),
            patch_legalm_lite_improve("skip"),
        )
    ),
    algorithmic_changes=(
        "legalm_stage1_recovery:bounded_expanding_windows",
        "legalm_complexity:bounded_stage1_stage2_stage3_hotsets",
        "legalm_total_overflow:maintained_counter_no_core_scan",
        "legalm_multiplier_update:bounded_rotating_core_sample",
        "legalm_stage3_score:disp_guard",
        "legalm_refine_window:tight",
        "legalm_stencil:local_dense",
        "legalm_escape:strict",
        "legalm_default_polish:disabled",
    ),
    source_family="legalm_engine",
    startpoint="materialized_legalm_engine_scale_safe_base",
)


def register_bringup_alias(
    alias: str,
    parent: str,
    *,
    summary: str,
    family: str | None = None,
    startpoint: str | None = None,
) -> None:
    parent_spec = VARIANTS[parent]
    VARIANTS[alias] = VariantSpec(
        name=alias,
        family=family or parent_spec.family,
        touched_symbol=parent_spec.touched_symbol,
        summary=summary,
        apply=parent_spec.apply,
        algorithmic_changes=(
            *tuple(parent_spec.algorithmic_changes),
            f"bringup_alias_parent:{parent}",
            "promotion_status:not_algorithm_promotion",
        ),
        source_family=parent_spec.source_family,
        startpoint=startpoint or f"bringup_alias_of_{parent}",
        entrypoint_contract=parent_spec.entrypoint_contract,
    )


register_bringup_alias(
    "negotiation_row_bucket_quality_frontier_r6_twopass",
    "negotiation_row_bucket_quality_frontier_r5",
    family="negotiation_row_bucket",
    summary=(
        "Base bring-up alias for planned R6 two-pass frontier.  It currently "
        "uses the r5 generated implementation so materializer/build/gate "
        "plumbing can be validated before the true R6 mutation replaces it."
    ),
)
register_bringup_alias(
    "negotiation_row_bucket_quality_frontier_r6_twopass_rowindex",
    "negotiation_row_bucket_quality_frontier_r5",
    family="negotiation_row_bucket",
    summary=(
        "Compatibility alias for the planned R6 two-pass row-index family; "
        "currently routes to r5 for harness bring-up only."
    ),
)
register_bringup_alias(
    "netaware14_rowedge_shortlist_hpwl",
    "netaware03_row_guard_frontier",
    family="netaware_objective",
    summary=(
        "Base bring-up alias for planned netaware14.  It uses the current "
        "clean-generator row-guard frontier while the standalone cached-HPWL "
        "implementation is developed."
    ),
)
register_bringup_alias(
    "priority_escape_telemetry_first",
    "priority_escape_scale_safe_base",
    family="priority_escape",
    summary=(
        "Base bring-up alias for planned priority telemetry-first repair.  It "
        "uses the current scale-safe priority base and is not a promotion "
        "result for the future telemetry mechanism."
    ),
)
register_bringup_alias(
    "localized_swap_transactional_polish",
    "localswap01_bounded_local_polish",
    family="localized_swap",
    summary=(
        "Base bring-up alias for planned transactional localized polish.  It "
        "uses the current bounded local-polish recipe until the transactional "
        "implementation is committed."
    ),
)
register_bringup_alias(
    "legalm_r6_relaxed_scanline_alm",
    "legalm_base_bounded_stage1",
    family="legalm_engine",
    summary=(
        "Base bring-up alias for planned LEGALM relaxed scanline/ALM R6.  It "
        "uses the current bounded Stage1 LEGALM variant until relaxed Stage1 "
        "is implemented."
    ),
)

DEFAULT_VARIANT_NAMES = list(ALGORITHMIC_VARIANTS.keys())[:50]
FAMILY_GROUPS: dict[str, list[str]] = {
    "algorithmic50": DEFAULT_VARIANT_NAMES,
    "base_bringup": [
        "negotiation_row_bucket_quality_frontier_r6_twopass",
        "netaware14_rowedge_shortlist_hpwl",
        "legalm_r6_relaxed_scanline_alm",
        "priority_escape_telemetry_first",
        "localized_swap_transactional_polish",
    ],
    "netaware10": list(NETAWARE_VARIANTS.keys()),
    # Compatibility alias: the localized_swap family is intentionally
    # compressed to one bounded local-polish recipe rather than ten similar
    # postopt/objective composites.
    "localized_swap10": list(LOCALIZED_SWAP_VARIANTS.keys()),
    "localized_swap_polish": list(LOCALIZED_SWAP_VARIANTS.keys()),
    "priority_escape10": list(PRIORITY_ESCAPE_VARIANTS.keys()),
    "priority_scale_safe_base": ["priority_escape_scale_safe_base"],
    "legalm10": list(LEGALM_VARIANTS.keys()),
    "legalm_base": ["legalm_base_bounded_stage1"],
    # Conservative starting points for normal evolve loops.  This group must
    # stay on the same negotiation/evolve algorithm path: runtime robustness
    # should come from bucketed active sets, bounded frontiers, candidate caps,
    # or dirty-region scans, not from routing large designs to diamond DPL.
    # LEGALM is intentionally opt-in until its DPL-1803 legality failure is
    # fixed; do not let the default matrix start from a known failed base.
    "robust_base": [
        "negotiation_row_bucket_quality_frontier_r5",
        "negotiation_row_bucket_active_set",
        "search_narrow_runtime",
        "netaware02_history_sqrt_anchor",
    ],
    "flow_ready_candidates": [
        "negotiation_row_bucket_quality_frontier_r5",
        "negotiation_row_bucket_active_set",
        "netaware02_history_sqrt_anchor",
    ],
    "netaware_base_robust": [
        "negotiation_row_bucket_quality_frontier_r5",
        "negotiation_row_bucket_active_set",
        "netaware02_history_sqrt_anchor",
        "netaware03_row_guard_frontier",
    ],
    # Priority escape is currently a repair target rather than a default base:
    # priority01 timed out on jpeg and priority06 had severe HPWL degradation.
    # Lead with the scale-safe base candidate; keep older probes opt-in until
    # runtime/HPWL guards are implemented.
    "priority_repair": [
        "priority_escape_scale_safe_base",
        "priority03_ladder_drc",
        "priority06_rowedge_fast",
        "priority08_midpoint_quad",
    ],
    "postopt_polish": list(LOCALIZED_SWAP_VARIANTS.keys()),
    "structural_experimental": list(LEGALM_VARIANTS.keys()),
    "diagnostic_fallback": [
        "large_design_diamond_fallback",
    ],
    "runtime_diagnostics": [
        "large_design_diamond_fallback",
    ],
}
FAMILY_GROUPS["family40"] = (
    FAMILY_GROUPS["netaware10"]
    + FAMILY_GROUPS["localized_swap10"]
    + FAMILY_GROUPS["priority_escape10"]
    + FAMILY_GROUPS["legalm10"]
)


def parse_problem(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("'\"")
        if key in {"name", "design", "platform"}:
            values[key] = value
    for key in ("name", "design", "platform"):
        if key not in values:
            raise RuntimeError(f"Problem file missing top-level {key}: {path}")
    return values


def find_python_with_yaml() -> str:
    candidates = []
    env_value = os.environ.get("DPL_EVOLVE_PYTHON_CANDIDATES", "")
    candidates.extend([item for item in env_value.split(os.pathsep) if item])
    candidates.extend(
        [
            sys.executable,
            "/opt/conda/miniforge3/envs/dreamplace/bin/python",
            "python3",
            "python",
        ]
    )
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        resolved = shutil.which(candidate) if "/" not in candidate else candidate
        if not resolved or not Path(resolved).exists():
            continue
        probe = subprocess.run(
            [resolved, "-c", "import yaml"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if probe.returncode == 0:
            return str(Path(resolved).resolve())
    raise RuntimeError("Could not find a Python interpreter with PyYAML for evaluator.py")


def run_command(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    elapsed = time.time() - started
    log_path.write_text(
        "$ " + " ".join(cmd) + "\n\n" + proc.stdout + f"\n[elapsed_seconds] {elapsed:.3f}\n",
        encoding="utf-8",
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout)
    return proc


def ensure_symlink(path: Path, target: Path) -> None:
    if path.is_symlink():
        if path.resolve() == target.resolve():
            return
        path.unlink()
    if path.exists():
        return
    path.symlink_to(target)


def ensure_registered_common_core(orfs_root: Path, state_root: Path) -> Path:
    openroad_src = orfs_root / "tools" / "OpenROAD"
    head = subprocess.check_output(
        ["git", "-C", str(openroad_src), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()
    core_root = state_root / "openroad_core" / head
    core_root.mkdir(parents=True, exist_ok=True)

    core_build = orfs_root / "tools" / "OpenROAD" / "build"
    core_install = orfs_root / "tools" / "install" / "OpenROAD"
    if not (core_build / "compile_commands.json").is_file():
        raise RuntimeError(f"Missing existing OpenROAD build compile_commands.json: {core_build}")
    if not (core_install / "bin" / "openroad").is_file():
        raise RuntimeError(f"Missing existing OpenROAD binary: {core_install / 'bin' / 'openroad'}")

    ensure_symlink(core_root / "build", core_build)
    install_parent = core_root / "install"
    install_parent.mkdir(exist_ok=True)
    ensure_symlink(install_parent / "OpenROAD", core_install)
    (core_root / "core_env.sh").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "# Registered by run_variant_experiment_matrix.py from an existing ORFS build.",
                f"export OPENROAD_CORE_ROOT={core_root}",
                f"export OPENROAD_BUILD_DIR={core_root / 'build'}",
                f"export OPENROAD_INSTALL_ROOT={core_root / 'install' / 'OpenROAD'}",
                f"export OPENROAD_BINARY={core_root / 'install' / 'OpenROAD' / 'bin' / 'openroad'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (core_root / "core_env.sh").chmod(0o755)
    return core_root


def discover_flow_variant(orfs_root: Path, problem: dict[str, str]) -> str:
    root = orfs_root / "flow" / "results" / problem["platform"] / problem["design"]
    candidates = sorted(root.glob("*/3_4_place_resized.odb"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"No reusable 3_4_place_resized.odb under {root}")
    preferred = root / "place_batch_20260421_220319" / "3_4_place_resized.odb"
    if preferred.exists():
        return preferred.parent.name
    base = root / "base" / "3_4_place_resized.odb"
    if base.exists():
        return base.parent.name
    return candidates[0].parent.name


def copy_variant_source(base_src: Path, variant_src: Path) -> None:
    if variant_src.exists():
        shutil.rmtree(variant_src)
    shutil.copytree(base_src, variant_src, symlinks=True)


def route_legalm_to_common_evolve_entrypoint(src: Path) -> list[str]:
    """Keep the evaluator command fixed while swapping the linked implementation.

    LEGALM is a materialized family source.  It must be evaluated through the
    same strict evolve command as every other variant, so `-use_negotiation`
    becomes the common entrypoint and this private source routes that entrypoint
    to the LEGALM implementation internally.
    """
    path = variant_file(src, "Opendp.cpp")
    replace_once(
        path,
        "  use_negotiation_ = use_negotiation;\n  importDb();",
        "  use_negotiation_ = false;\n"
        "  const bool use_legalm_impl = use_legalm || use_negotiation;\n"
        "  importDb();",
    )
    replace_once(path, "  if (use_negotiation && use_legalm) {", "  if (false && use_legalm_impl) {")
    replace_once(
        path,
        "  if (!use_negotiation_ && !use_legalm) {",
        "  if (!use_negotiation_ && !use_legalm_impl) {",
    )
    return [str(path)]


def materialize_source_family_base(
    *,
    spec: VariantSpec,
    variant_root: Path,
    agent_root: Path,
    orfs_root: Path,
    state_root: Path,
    env: dict[str, str],
) -> tuple[Path, list[str]]:
    clean_base = orfs_root / "tools" / "OpenROAD" / "src" / "dpl_evolve"
    if spec.source_family == "clean_evolve_base":
        return clean_base, []

    family_base = variant_root / "family_base" / spec.source_family / "dpl_evolve"
    materialize_cmd = [
        str(agent_root / "scripts" / "materialize_family_variant.sh"),
        "--family",
        spec.source_family,
        "--output-dir",
        str(family_base),
        "--force",
    ]
    log_path = variant_root / "logs" / f"{spec.source_family}__materialize.log"
    run_command(materialize_cmd, cwd=agent_root, env=env, log_path=log_path)

    touched: list[str] = []
    if spec.source_family == "legalm_engine":
        touched.extend(route_legalm_to_common_evolve_entrypoint(family_base))
    return family_base, touched


def configure_and_build_variant(
    *,
    spec: VariantSpec,
    exp_root: Path,
    agent_root: Path,
    orfs_root: Path,
    state_root: Path,
    core_root: Path,
    threads: int,
    env: dict[str, str],
) -> dict[str, Any]:
    variant_root = exp_root / "variants" / spec.name
    variant_src = variant_root / "src" / "dpl_evolve"
    base_src, startpoint_touched = materialize_source_family_base(
        spec=spec,
        variant_root=variant_root,
        agent_root=agent_root,
        orfs_root=orfs_root,
        state_root=state_root,
        env=env,
    )
    copy_variant_source(base_src, variant_src)
    touched_files = sorted(set(startpoint_touched + spec.apply(variant_src)))
    patch_diff = variant_root / "patch.diff"
    diff_proc = subprocess.run(
        ["diff", "-ruN", str(base_src), str(variant_src)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    patch_diff.write_text(diff_proc.stdout, encoding="utf-8")
    patch_sha256 = sha256_file(patch_diff)

    manifest = {
        "schema_version": 2,
        "variant": spec.name,
        "variant_uid": spec.name,
        "family": spec.family,
        "source_family": spec.source_family,
        "startpoint": spec.startpoint,
        "entrypoint_contract": spec.entrypoint_contract,
        "touched_symbol": spec.touched_symbol,
        "summary": spec.summary,
        "algorithmic_changes": list(spec.algorithmic_changes),
        "touched_files": touched_files,
        "patch_diff": str(patch_diff),
        "patch_sha256": patch_sha256,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    (variant_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    configure_log = exp_root / "logs" / "build" / f"{spec.name}__configure.log"
    build_log = exp_root / "logs" / "build" / f"{spec.name}__build.log"
    configure_cmd = [
        str(agent_root / "scripts" / "configure_openroad_variant_relink.sh"),
        "--variant-root",
        str(variant_root),
        "--dpl-src",
        str(variant_src),
        "--core-root",
        str(core_root),
    ]
    run_command(configure_cmd, cwd=agent_root, env=env, log_path=configure_log)
    build_cmd = [
        str(agent_root / "scripts" / "build_openroad_variant_relink.sh"),
        "--variant-root",
        str(variant_root),
        "--dpl-src",
        str(variant_src),
        "--core-root",
        str(core_root),
        "--threads",
        str(threads),
    ]
    run_command(build_cmd, cwd=agent_root, env=env, log_path=build_log)

    binary = variant_root / "install" / "OpenROAD" / "bin" / "openroad"
    if not binary.is_file():
        raise RuntimeError(f"Variant build completed but binary is missing: {binary}")
    return {
        "variant": spec.name,
        "variant_root": str(variant_root),
        "variant_src": str(variant_src),
        "openroad_binary": str(binary),
        "manifest": manifest,
        "patch_diff": str(patch_diff),
        "patch_sha256": patch_sha256,
        "configure_log": str(configure_log),
        "build_log": str(build_log),
    }


def run_evaluator(
    *,
    python_bin: str,
    agent_root: Path,
    orfs_root: Path,
    env: dict[str, str],
    problem_path: Path,
    flow_variant: str,
    run_tag: str,
    openroad_binary: Path,
    threads: int,
    eval_timeout_sec: int,
    out_path: Path,
    log_path: Path,
) -> dict[str, Any]:
    cmd = [
        python_bin,
        str(agent_root / "adapters" / "science_codeevolve" / "evaluator.py"),
        "--problem",
        str(problem_path),
        "--config",
        str(agent_root / "configs" / "codex_design_specific.yaml"),
        "--mode",
        "single",
        "--line",
        "evolve_line",
        "--flow-variant",
        flow_variant,
        "--run-tag",
        run_tag,
        "--threads",
        str(threads),
        "--evolve-engine",
        "negotiation",
        "--skip-build",
        "--eval-timeout-sec",
        str(eval_timeout_sec),
        "--openroad-binary",
        str(openroad_binary),
        "--out",
        str(out_path),
    ]
    run_command(cmd, cwd=orfs_root, env=env, log_path=log_path, check=False)
    if not out_path.is_file():
        return {
            "status": "evaluator_failed",
            "summary": {},
            "error": f"evaluator did not create {out_path}",
        }
    try:
        return json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "evaluator_failed", "summary": {}, "error": str(exc)}


def failure_signature(eval_data: dict[str, Any], *, improved: bool | None) -> str | None:
    if eval_data.get("status") != "ok":
        run_result = eval_data.get("command_results", {}).get("run", {}) or {}
        stdout_tail = str(run_result.get("stdout_tail") or "")
        stderr_tail = str(run_result.get("stderr_tail") or "")
        if run_result.get("timed_out"):
            return "eval_timeout"
        if "DPL-0033" in stdout_tail or "check placement" in stdout_tail.lower():
            return "placement_check_failed"
        if "Violations remain" in stdout_tail:
            return "legalizer_did_not_converge"
        if "Terminated" in stderr_tail:
            return "run_terminated"
        return str(eval_data.get("status") or eval_data.get("error") or "evaluator_failed")
    if not legality_ok(eval_data):
        return "legality_or_placement_gate_failed"
    if improved is False:
        return "legal_but_no_score_improvement"
    return None


def write_markdown_summary(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"# Variant Experiment Matrix: {summary['experiment_id']}",
        "",
        "This run applies deterministic dpl_evolve-only mutations to private source",
        "copies, relinks private OpenROAD binaries, evaluates them from fixed",
        "placement snapshots, and writes RunDB/KnowledgeDB evidence.",
    ]
    parallelism = summary.get("parallelism") or {}
    if parallelism:
        lines.extend(
            [
                "",
                "## Parallelism",
                f"- Build jobs: `{parallelism.get('build_jobs')}`",
                f"- Build threads per job: `{parallelism.get('build_threads')}`",
                f"- Evaluator jobs: `{parallelism.get('eval_jobs')}`",
                f"- OpenROAD threads per evaluator: `{parallelism.get('eval_threads')}`",
                f"- Evaluation timeout: `{parallelism.get('eval_timeout_sec')}s`",
                "",
                "## Cases",
            ]
        )
    for case in summary["cases"]:
        lines.append(f"- `{case['case']}`: flow_variant `{case['flow_variant']}`")
    lines.extend(["", "## Variants"])
    for variant in summary["variants"]:
        lines.append(
            f"- `{variant['variant']}`: {variant['summary']} "
            f"({variant['family']}, source `{variant.get('source_family', 'clean_evolve_base')}`, "
            f"`{variant['touched_symbol']}`)"
        )
        lines.append(
            f"  Entrypoint: `{variant.get('entrypoint_contract', 'detailed_placement_evolve -use_negotiation')}`"
        )
        changes = variant.get("algorithmic_changes") or []
        if changes:
            lines.append(f"  Changes: `{', '.join(changes)}`")
    if summary.get("build_only"):
        lines.extend(["", "## Build Results", ""])
        lines.append("| Variant | Built | Binary | Error |")
        lines.append("| --- | ---: | --- | --- |")
        for variant in summary["variants"]:
            name = variant["variant"]
            build_info = (summary.get("build_results") or {}).get(name) or {}
            error = (summary.get("build_errors") or {}).get(name) or ""
            binary = build_info.get("openroad_binary", "")
            lines.append(f"| `{name}` | {'yes' if binary else 'no'} | `{binary}` | {error} |")
    lines.extend(["", "## Results", ""])
    lines.append("| Case | Variant | Legal | Score | HPWL delta | Runtime | Failure |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for item in summary["results"]:
        metrics = item.get("metrics") or {}
        legal = "yes" if item.get("legal") else "no"
        score = item.get("score")
        score_text = "" if score is None else f"{float(score):.6f}"
        hpwl = metrics.get("hpwl_delta_micron")
        hpwl_text = "" if hpwl is None else f"{float(hpwl):.3f}"
        runtime = metrics.get("runtime_seconds")
        runtime_text = "" if runtime is None else f"{float(runtime):.3f}"
        failure = item.get("failure_signature") or ""
        lines.append(
            f"| `{item['case']}` | `{item['variant']}` | {legal} | {score_text} | "
            f"{hpwl_text} | {runtime_text} | {failure} |"
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            f"- Summary JSON: `{summary['summary_json']}`",
            f"- Variant index: `{summary.get('variant_index', '')}`",
            f"- RunDB: `{summary['run_db']}`",
            f"- Token ROI: `{summary.get('token_roi_md', '')}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic dpl_evolve variant experiments and update evidence databases."
    )
    parser.add_argument("--experiment-id", default=f"variant_matrix_{now_stamp()}")
    parser.add_argument("--cases", nargs="+", default=DEFAULT_CASES)
    parser.add_argument("--variants", nargs="+", default=None)
    parser.add_argument(
        "--family-groups",
        nargs="+",
        default=[],
        help="Expand named family groups, for example netaware10 localized_swap10 priority_escape10 legalm10.",
    )
    parser.add_argument("--build-jobs", type=int, default=4)
    parser.add_argument("--eval-jobs", type=int, default=8)
    parser.add_argument("--build-threads", type=int, default=10)
    parser.add_argument("--eval-threads", type=int, default=10)
    parser.add_argument("--eval-timeout-sec", type=int, default=900)
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-variants", action="store_true")
    parser.add_argument("--list-family-groups", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.list_family_groups:
        for group, names in sorted(FAMILY_GROUPS.items()):
            print(f"{group}\t{len(names)}\t{','.join(names)}")
        return
    if args.list_variants:
        for name, spec in sorted(VARIANTS.items()):
            print(
                f"{name}\t{spec.family}\t{spec.source_family}\t"
                f"{spec.touched_symbol}\t{spec.summary}"
            )
        return

    selected_variant_names: list[str] = []
    if args.family_groups:
        unknown_groups = [name for name in args.family_groups if name not in FAMILY_GROUPS]
        if unknown_groups:
            raise SystemExit(f"Unknown family group(s): {', '.join(unknown_groups)}")
        for group in args.family_groups:
            selected_variant_names.extend(FAMILY_GROUPS[group])
    if args.variants is not None:
        selected_variant_names.extend(args.variants)
    if not selected_variant_names:
        selected_variant_names = list(DEFAULT_VARIANT_NAMES)
    selected_variant_names = list(dict.fromkeys(selected_variant_names))

    unknown = [name for name in selected_variant_names if name not in VARIANTS]
    if unknown:
        raise SystemExit(f"Unknown variant(s): {', '.join(unknown)}")

    runtime = resolve_runtime_paths(
        anchor_file=__file__,
        agent_root_levels_up=1,
        script_name="run_variant_experiment_matrix.py",
    )
    agent_root = runtime.agent_root
    orfs_root = runtime.orfs_root
    state_root = runtime.state_root
    exp_root = state_root / "experiments" / args.experiment_id
    exp_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DPL_EVOLVE_AGENT_ROOT"] = str(agent_root)
    env["ORFS_ROOT"] = str(orfs_root)
    env["DPL_EVOLVE_STATE_ROOT"] = str(state_root)
    env["DPL_EVOLVE_SKIP_ENV_SH"] = "1"

    python_bin = find_python_with_yaml()
    core_root = ensure_registered_common_core(orfs_root, state_root)
    core_binary = core_root / "install" / "OpenROAD" / "bin" / "openroad"

    problems: dict[str, dict[str, Any]] = {}
    for case in args.cases:
        problem_path = agent_root / "problems" / case / "problem.yaml"
        if not problem_path.is_file():
            raise SystemExit(f"Missing problem file for case {case}: {problem_path}")
        problem = parse_problem(problem_path)
        flow_variant = discover_flow_variant(orfs_root, problem)
        problems[case] = {
            "case": case,
            "problem": problem,
            "problem_path": problem_path,
            "flow_variant": flow_variant,
        }

    selected_specs = [VARIANTS[name] for name in selected_variant_names]
    planned = {
        "experiment_id": args.experiment_id,
        "agent_root": str(agent_root),
        "orfs_root": str(orfs_root),
        "state_root": str(state_root),
        "core_root": str(core_root),
        "python_bin": python_bin,
        "parallelism": {
            "build_jobs": args.build_jobs,
            "build_threads": args.build_threads,
            "eval_jobs": args.eval_jobs,
            "eval_threads": args.eval_threads,
            "eval_timeout_sec": args.eval_timeout_sec,
        },
        "entrypoint_contract": "all variants use detailed_placement_evolve -use_negotiation",
        "family_groups": list(args.family_groups),
        "cases": [
            {"case": case, "flow_variant": item["flow_variant"], **item["problem"]}
            for case, item in problems.items()
        ],
        "variants": [
            {
                "variant": spec.name,
                "family": spec.family,
                "source_family": spec.source_family,
                "startpoint": spec.startpoint,
                "entrypoint_contract": spec.entrypoint_contract,
                "touched_symbol": spec.touched_symbol,
                "summary": spec.summary,
                "algorithmic_changes": list(spec.algorithmic_changes),
            }
            for spec in selected_specs
        ],
        "build_only": bool(args.build_only),
        "dry_run": bool(args.dry_run),
    }
    (exp_root / "plan.json").write_text(json.dumps(planned, indent=2) + "\n", encoding="utf-8")
    variant_index_path = exp_root / "variant_index.jsonl"
    variant_index_path.write_text("", encoding="utf-8")
    for serial, spec in enumerate(selected_specs, start=1):
        index_row = {
            "schema_version": 1,
            "experiment_id": args.experiment_id,
            "variant_serial": serial,
            "variant_uid": spec.name,
            "display_name": spec.name,
            "status": "planned",
            "wave": "normal_matrix",
            "family": spec.family,
            "source_family": spec.source_family,
            "startpoint": spec.startpoint,
            "entrypoint_contract": spec.entrypoint_contract,
            "mechanism": spec.summary,
            "touched_symbol": spec.touched_symbol,
            "algorithmic_changes": list(spec.algorithmic_changes),
            "source": "scripts/run_variant_experiment_matrix.py",
            "manifest_path": str(exp_root / "variants" / spec.name / "manifest.json"),
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        with variant_index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_row, sort_keys=True) + "\n")
    if args.dry_run:
        print(json.dumps(planned, indent=2))
        return

    baseline_metrics: dict[str, dict[str, float]] = {}
    baseline_eval_by_case: dict[str, dict[str, Any]] = {}
    if not args.skip_baseline and not args.build_only:
        def eval_baseline_one(case: str, item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            out_path = exp_root / "eval" / "baseline" / f"{case}.json"
            log_path = exp_root / "logs" / "eval" / f"baseline__{case}.log"
            run_tag = f"{args.experiment_id}__baseline__{case}"
            data = run_evaluator(
                python_bin=python_bin,
                agent_root=agent_root,
                orfs_root=orfs_root,
                env=env,
                problem_path=item["problem_path"],
                flow_variant=item["flow_variant"],
                run_tag=run_tag,
                openroad_binary=core_binary,
                threads=args.eval_threads,
                eval_timeout_sec=args.eval_timeout_sec,
                out_path=out_path,
                log_path=log_path,
            )
            return case, data

        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.eval_jobs)) as pool:
            future_to_case = {
                pool.submit(eval_baseline_one, case, item): case
                for case, item in problems.items()
            }
            for future in concurrent.futures.as_completed(future_to_case):
                case = future_to_case[future]
                try:
                    case, data = future.result()
                except Exception as exc:  # noqa: BLE001 - preserve baseline failure evidence.
                    data = {
                        "status": "baseline_failed",
                        "summary": {},
                        "error": str(exc),
                    }
                baseline_eval_by_case[case] = data
                if data.get("status") == "ok" and legality_ok(data):
                    baseline_metrics[case] = build_metric_vector(data)

    build_results: dict[str, dict[str, Any]] = {}
    build_errors: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.build_jobs)) as pool:
        future_to_spec = {
            pool.submit(
                configure_and_build_variant,
                spec=spec,
                exp_root=exp_root,
                agent_root=agent_root,
                orfs_root=orfs_root,
                state_root=state_root,
                core_root=core_root,
                threads=args.build_threads,
                env=env,
            ): spec
            for spec in selected_specs
        }
        for future in concurrent.futures.as_completed(future_to_spec):
            spec = future_to_spec[future]
            try:
                build_results[spec.name] = future.result()
            except Exception as exc:  # noqa: BLE001 - write evidence and continue.
                build_errors[spec.name] = str(exc)

    if args.build_only:
        summary = {
            "experiment_id": args.experiment_id,
            "agent_root": str(agent_root),
            "orfs_root": str(orfs_root),
            "state_root": str(state_root),
            "core_root": str(core_root),
            "parallelism": planned["parallelism"],
            "entrypoint_contract": planned["entrypoint_contract"],
            "family_groups": planned["family_groups"],
            "cases": planned["cases"],
            "variants": planned["variants"],
            "build_only": True,
            "build_results": build_results,
            "build_errors": build_errors,
            "baseline": {},
            "results": [],
            "summary_json": str(exp_root / "summary.json"),
            "summary_md": str(exp_root / "SUMMARY.md"),
            "variant_index": str(variant_index_path),
            "run_db": str(run_db_path(state_root)),
            "token_roi_md": "",
            "token_roi_json": "",
        }
        (exp_root / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_markdown_summary(exp_root / "SUMMARY.md", summary)
        print(f"[INFO] Build-only matrix complete: {exp_root}")
        print(f"[INFO] Summary: {exp_root / 'SUMMARY.md'}")
        return

    records: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []

    def eval_one(spec: VariantSpec, case: str, item: dict[str, Any]) -> dict[str, Any]:
        build_info = build_results.get(spec.name)
        run_tag = f"{args.experiment_id}__{spec.name}__{case}"
        run_record_path = exp_root / "run_records" / f"{run_tag}.json"
        if build_info is None:
            reason = build_errors.get(spec.name, "variant_build_failed")
            record = {
                "run_id": run_tag,
                "experiment_id": args.experiment_id,
                "problem": case,
                "patch_family": spec.family,
                "source_family": spec.source_family,
                "startpoint": spec.startpoint,
                "entrypoint_contract": spec.entrypoint_contract,
                "variant": spec.name,
                "touched_symbol": spec.touched_symbol,
                "target_file": "tools/OpenROAD/src/dpl_evolve",
                "status": "rejected",
                "improved": False,
                "failure_signature": reason,
                "summary": spec.summary,
                "algorithmic_changes": list(spec.algorithmic_changes),
                "metrics": {},
                "artifacts": {
                    "experiment_root": str(exp_root),
                    "manifest": str(exp_root / "variants" / spec.name / "manifest.json"),
                },
            }
            run_record_path.parent.mkdir(parents=True, exist_ok=True)
            run_record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            return record

        out_path = exp_root / "eval" / spec.name / f"{case}.json"
        log_path = exp_root / "logs" / "eval" / f"{spec.name}__{case}.log"
        eval_data = run_evaluator(
            python_bin=python_bin,
            agent_root=agent_root,
            orfs_root=orfs_root,
            env=env,
            problem_path=item["problem_path"],
            flow_variant=item["flow_variant"],
            run_tag=run_tag,
            openroad_binary=Path(build_info["openroad_binary"]),
            threads=args.eval_threads,
            eval_timeout_sec=args.eval_timeout_sec,
            out_path=out_path,
            log_path=log_path,
        )
        metrics: dict[str, float] = {}
        score = None
        score_components = None
        legal = legality_ok(eval_data)
        improved: bool | None = None
        if eval_data.get("status") == "ok":
            metrics = build_metric_vector(eval_data)
            reference = baseline_metrics.get(case)
            if reference is not None and legal:
                score, score_components = composite_score(reference, metrics)
                improved = score > 0.0
            elif legal:
                improved = False
            else:
                improved = False
        else:
            improved = False
        signature = failure_signature(eval_data, improved=improved)
        if eval_data.get("status") == "ok" and legal and case not in baseline_metrics:
            signature = "missing_baseline_reference"
        status = "accepted" if improved else "rejected"
        record = {
            "run_id": run_tag,
            "experiment_id": args.experiment_id,
            "problem": case,
            "platform": item["problem"]["platform"],
            "design": item["problem"]["design"],
            "flow_variant": item["flow_variant"],
            "patch_family": spec.family,
            "source_family": spec.source_family,
            "startpoint": spec.startpoint,
            "entrypoint_contract": spec.entrypoint_contract,
            "variant": spec.name,
            "touched_symbol": spec.touched_symbol,
            "target_file": "tools/OpenROAD/src/dpl_evolve",
            "status": status,
            "improved": bool(improved),
            "score": score,
            "score_components": score_components,
            "failure_signature": signature,
            "summary": spec.summary,
            "algorithmic_changes": list(spec.algorithmic_changes),
            "metrics": metrics,
            "artifacts": {
                "experiment_root": str(exp_root),
                "variant_root": build_info.get("variant_root"),
                "openroad_binary": build_info.get("openroad_binary"),
                "evaluator_json": str(out_path),
                "eval_log": str(log_path),
                "build_log": build_info.get("build_log"),
                "configure_log": build_info.get("configure_log"),
                "patch_diff": build_info.get("patch_diff"),
                "patch_sha256": build_info.get("patch_sha256"),
                "manifest": build_info.get("manifest"),
            },
        }
        run_record_path.parent.mkdir(parents=True, exist_ok=True)
        run_record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record

    eval_tasks: list[tuple[VariantSpec, str, dict[str, Any]]] = [
        (spec, case, item)
        for spec in selected_specs
        for case, item in problems.items()
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.eval_jobs)) as pool:
        future_to_task = {
            pool.submit(eval_one, spec, case, item): (spec, case)
            for spec, case, item in eval_tasks
        }
        for future in concurrent.futures.as_completed(future_to_task):
            spec, case = future_to_task[future]
            try:
                record = future.result()
            except Exception as exc:  # noqa: BLE001 - persist a rejected run record.
                record = {
                    "run_id": f"{args.experiment_id}__{spec.name}__{case}",
                    "experiment_id": args.experiment_id,
                    "problem": case,
                    "patch_family": spec.family,
                    "source_family": spec.source_family,
                    "startpoint": spec.startpoint,
                    "entrypoint_contract": spec.entrypoint_contract,
                    "variant": spec.name,
                    "touched_symbol": spec.touched_symbol,
                    "target_file": "tools/OpenROAD/src/dpl_evolve",
                    "status": "rejected",
                    "improved": False,
                    "failure_signature": str(exc),
                    "summary": spec.summary,
                    "algorithmic_changes": list(spec.algorithmic_changes),
                    "metrics": {},
                    "artifacts": {"experiment_root": str(exp_root)},
                }
            records.append(record)
            append_run_record(run_db_path(state_root), record)
            process_run_record(state_root, record)
            result_rows.append(
                {
                    "case": record["problem"],
                    "variant": record["variant"],
                    "family": record["patch_family"],
                    "source_family": record.get("source_family"),
                    "legal": record.get("failure_signature") not in {"legality_or_placement_gate_failed"}
                    and bool(record.get("metrics")),
                    "score": record.get("score"),
                    "metrics": record.get("metrics"),
                    "failure_signature": record.get("failure_signature"),
                    "run_id": record.get("run_id"),
                }
            )

    token_roi = write_token_roi_reports(state_root=state_root, out_dir=exp_root / "reports")
    summary = {
        "experiment_id": args.experiment_id,
        "agent_root": str(agent_root),
        "orfs_root": str(orfs_root),
        "state_root": str(state_root),
        "core_root": str(core_root),
        "parallelism": planned["parallelism"],
        "entrypoint_contract": planned["entrypoint_contract"],
        "family_groups": planned["family_groups"],
        "cases": planned["cases"],
        "variants": planned["variants"],
        "build_only": False,
        "build_results": build_results,
        "build_errors": build_errors,
        "baseline": {
            case: {
                "status": data.get("status"),
                "legal": legality_ok(data),
                "metrics": baseline_metrics.get(case),
                "summary": data.get("summary", {}),
            }
            for case, data in baseline_eval_by_case.items()
        },
        "results": sorted(result_rows, key=lambda x: (x["case"], x["variant"])),
        "summary_json": str(exp_root / "summary.json"),
        "summary_md": str(exp_root / "SUMMARY.md"),
        "variant_index": str(variant_index_path),
        "run_db": str(run_db_path(state_root)),
        "token_roi_md": str(token_roi.get("markdown", "")),
        "token_roi_json": str(token_roi.get("json", "")),
    }
    summary_path = exp_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown_summary(exp_root / "SUMMARY.md", summary)
    print(f"[INFO] Matrix experiment complete: {exp_root}")
    print(f"[INFO] Summary: {exp_root / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
