// Test doubles for the topology queried by the exact patched native predicate.
#include <cstdlib>
#include <iostream>
#include <vector>

namespace sta {
struct LibertyCell {
  bool sequential;
  bool hasSequentials() const { return sequential; }
};
} // namespace sta

namespace odb {
enum class Signal { signal, power, ground, clock };
struct SigType {
  Signal value;
  bool isSupply() const {
    return value == Signal::power || value == Signal::ground;
  }
};
struct dbInst;
struct dbNet;
struct dbMaster {
  sta::LibertyCell cell;
};
struct dbITerm {
  dbInst *inst;
  dbNet *net;
  dbNet *getNet() const { return net; }
  dbInst *getInst() const { return inst; }
};
struct dbNet {
  Signal signal;
  std::vector<dbITerm *> terms;
  SigType getSigType() const { return {signal}; }
  const std::vector<dbITerm *> &getITerms() const { return terms; }
};
struct dbInst {
  explicit dbInst(bool sequential) : master{{sequential}} {}
  dbMaster master;
  std::vector<dbITerm *> terms;
  const std::vector<dbITerm *> &getITerms() const { return terms; }
  dbMaster *getMaster() { return &master; }
};
} // namespace odb

namespace sta {
struct dbNetwork {
  odb::dbMaster *dbToSta(odb::dbMaster *master) { return master; }
  LibertyCell *libertyCell(odb::dbMaster *master) { return &master->cell; }
};
struct dbSta {
  dbNetwork network;
  dbNetwork *getDbNetwork() { return &network; }
};
} // namespace sta

namespace rmp {
struct Restructure {
  sta::dbSta *open_sta_;
  bool touchesSequentialPin(odb::dbInst *inst) const;
};
// INSERT_EXACT_NATIVE_PREDICATE
} // namespace rmp

int main(int argc, char **argv) {
  if (argc != 2) {
    return 2;
  }
  sta::dbSta timing;
  rmp::Restructure restructure{&timing};
  odb::dbInst target(false), ff(true), logic(false);
  odb::dbNet supply{odb::Signal::power, {}}, signal{odb::Signal::signal, {}};
  odb::dbITerm supply_target{&target, &supply}, supply_ff{&ff, &supply};
  odb::dbITerm signal_target{&target, &signal}, signal_ff{&ff, &signal};
  odb::dbITerm signal_logic{&logic, &signal}, disconnected{&target, nullptr};
  odb::dbITerm missing_instance{nullptr, &signal};
  supply.terms = {&supply_target, &supply_ff};
  signal.terms = {&signal_target, &signal_ff};
  switch (std::atoi(argv[1])) {
  case 0: // Unconnected instance.
    break;
  case 1: // Disconnected pin.
    target.terms = {&disconnected};
    break;
  case 2: // Only VDD shared with a flip-flop.
    target.terms = {&supply_target};
    break;
  case 3: // Only VSS shared with a flip-flop.
    supply.signal = odb::Signal::ground;
    target.terms = {&supply_target};
    break;
  case 4: // Actual sequential data connection must remain protected.
    target.terms = {&signal_target};
    break;
  case 5: // Ordinary combinational signal connection.
    target.terms = {&signal_target};
    signal.terms = {&signal_target, &signal_logic};
    break;
  case 6: // Shared VDD does not hide a real sequential signal neighbor.
    target.terms = {&supply_target, &signal_target};
    break;
  case 7: // Shared VSS plus ordinary combinational signal connection.
    supply.signal = odb::Signal::ground;
    target.terms = {&supply_target, &signal_target};
    signal.terms = {&signal_target, &signal_logic};
    break;
  case 8: // A clock net is not a supply exemption.
    signal.signal = odb::Signal::clock;
    target.terms = {&signal_target};
    break;
  case 9: // A removed neighbor is ignored without dereferencing it.
    target.terms = {&signal_target};
    signal.terms = {&signal_target, &missing_instance};
    break;
  default:
    return 2;
  }
  std::cout << restructure.touchesSequentialPin(&target) << '\n';
}
