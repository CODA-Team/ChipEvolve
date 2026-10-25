#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <vector>

namespace odb {
enum class dbSiteClass { CORE, PAD };
enum class dbOrientType { R0, MX };

struct Point {
  int x_, y_;
  int x() const { return x_; }
  int y() const { return y_; }
};

struct dbSite {
  dbSiteClass kind;
  dbSiteClass getClass() const { return kind; }
};

struct dbMaster {
  int width;
  int getWidth() const { return width; }
};

struct dbRow {
  dbSite *site;
  Point origin;
  int spacing, count;
  dbOrientType orient;
  dbSite *getSite() const { return site; }
  Point getOrigin() const { return origin; }
  int getSpacing() const { return spacing; }
  int getSiteCount() const { return count; }
  dbOrientType getOrient() const { return orient; }
};

struct dbBlock {
  std::vector<dbRow *> rows;
  const std::vector<dbRow *> &getRows() const { return rows; }
};
} // namespace odb

// INSERT_EXACT_NATIVE_PROJECTION

int main(int argc, char **argv) {
  if (argc != 2) {
    return 2;
  }
  odb::dbSite core{odb::dbSiteClass::CORE}, pad{odb::dbSiteClass::PAD};
  using Orient = odb::dbOrientType;
  odb::dbRow full{&core, {0, 0}, 10, 100, Orient::R0};
  odb::dbRow left{&core, {0, 0}, 10, 10, Orient::R0};
  odb::dbRow right{&core, {200, 0}, 10, 20, Orient::R0};
  odb::dbRow diagonal{&core, {200, 10}, 10, 20, Orient::MX};
  odb::dbRow narrow{&core, {0, 0}, 10, 1, Orient::R0};
  odb::dbRow pad_row{&pad, {0, 0}, 10, 100, Orient::R0};
  odb::dbRow negative{&core, {-100, 0}, 10, 20, Orient::R0};
  odb::dbRow upper{&core, {0, 20}, 10, 100, Orient::MX};
  odb::dbRow exact{&core, {100, 0}, 10, 2, Orient::R0};
  odb::dbBlock block;
  odb::dbMaster master{20};
  odb::dbBlock *target = &block;
  odb::dbMaster *cell = &master;
  int raw_x = 55, raw_y = 0;
  switch (std::atoi(argv[1])) {
  case 0:
    block.rows = {&full};
    break;
  case 1:
    block.rows = {&left, &right};
    raw_x = 250;
    break;
  case 2:
    block.rows = {&left, &diagonal};
    raw_x = 250;
    break;
  case 3:
    block.rows = {&narrow, &right};
    raw_x = 220;
    break;
  case 4:
    block.rows = {&narrow};
    raw_x = 0;
    break;
  case 5:
    block.rows = {&pad_row, &right};
    raw_x = 220;
    break;
  case 6:
    break;
  case 7:
    block.rows = {&negative};
    raw_x = -5;
    break;
  case 8:
    block.rows = {&full, &upper};
    raw_y = 8;
    break;
  case 9:
    block.rows = {&full, &upper};
    raw_y = 10;
    break;
  case 10:
    block.rows = {&exact};
    raw_x = 102;
    break;
  case 11:
    block.rows = {&full};
    cell = nullptr;
    break;
  case 12:
    target = nullptr;
    break;
  case 13:
    block.rows = {&right, &left};
    break;
  default:
    return 2;
  }
  int x = -999, y = -999;
  Orient orient = Orient::R0;
  const bool found =
      snapToPlacementRow(target, cell, raw_x, raw_y, x, y, orient);
  std::cout << found << ' ' << x << ' ' << y << ' ' << static_cast<int>(orient)
            << '\n';
}
