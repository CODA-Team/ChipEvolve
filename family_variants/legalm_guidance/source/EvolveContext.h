// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2018-2025, The OpenROAD Authors

#pragma once

#include <string>

namespace dpl_evolve {

struct EvolveContext
{
  // Control-plane values only.  Do not route per-cell/per-net hot data through
  // this context: stage implementations should build in-process contiguous
  // vectors, row/segment indexes, and node-id keyed side arrays from Opendp.
  int max_threads = 10;
  int max_displacement_x = 0;
  int max_displacement_y = 0;
  bool incremental = false;
  bool negotiation_requested = false;
  bool abacus_requested = false;
  std::string report_file_name;
};

}  // namespace dpl_evolve
