int snapDownToGrid(const int value, const int origin, const int step)
{
  if (step <= 0) {
    return value;
  }
  const int delta = value - origin;
  if (delta >= 0) {
    return origin + (delta / step) * step;
  }
  return origin - ((-delta + step - 1) / step) * step;
}

bool snapToPlacementRow(odb::dbBlock* block,
                        odb::dbMaster* master,
                        const int raw_x,
                        const int raw_y,
                        int& snapped_x,
                        int& snapped_y,
                        odb::dbOrientType& snapped_orient)
{
  if (block == nullptr || master == nullptr) {
    return false;
  }

  odb::dbRow* best_row = nullptr;
  int64_t best_dist = std::numeric_limits<int64_t>::max();
  const int master_width = static_cast<int>(master->getWidth());
  for (odb::dbRow* row : block->getRows()) {
    odb::dbSite* site = row->getSite();
    if (site == nullptr || site->getClass() == odb::dbSiteClass::PAD) {
      continue;
    }
    const odb::Point row_origin = row->getOrigin();
    const int64_t dy = static_cast<int64_t>(raw_y) - row_origin.y();
    const int64_t dist = dy * dy;
    if (dist < best_dist) {
      best_dist = dist;
      best_row = row;
    }
  }
  if (best_row == nullptr) {
    return false;
  }

  const odb::Point origin = best_row->getOrigin();
  const int spacing = best_row->getSpacing();
  const int site_count = best_row->getSiteCount();
  const int row_min_x = origin.x();
  int row_max_x = row_min_x;
  if (site_count > 0 && spacing > 0) {
    row_max_x = row_min_x + (site_count - 1) * spacing;
  }
  row_max_x = std::max(row_min_x, row_max_x - std::max(0, master_width - spacing));

  int x = snapDownToGrid(raw_x, row_min_x, spacing);
  x = std::clamp(x, row_min_x, row_max_x);
  x = snapDownToGrid(x, row_min_x, spacing);

  snapped_x = x;
  snapped_y = origin.y();
  snapped_orient = best_row->getOrient();
  return true;
}
