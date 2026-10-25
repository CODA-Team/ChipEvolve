// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2019-2026, The OpenROAD Authors
// Original predicate retained as a regression fixture for the compatibility fix.

bool Restructure::touchesSequentialPin(odb::dbInst* inst) const
{
  for (odb::dbITerm* iterm : inst->getITerms()) {
    odb::dbNet* net = iterm->getNet();
    if (net == nullptr) {
      continue;
    }

    for (odb::dbITerm* connected_iterm : net->getITerms()) {
      odb::dbInst* connected_inst = connected_iterm->getInst();
      if (connected_inst == nullptr || connected_inst == inst) {
        continue;
      }
      sta::LibertyCell* connected_cell = open_sta_->getDbNetwork()->libertyCell(
          open_sta_->getDbNetwork()->dbToSta(connected_inst->getMaster()));
      if (connected_cell != nullptr && connected_cell->hasSequentials()) {
        return true;
      }
    }
  }
  return false;
}
