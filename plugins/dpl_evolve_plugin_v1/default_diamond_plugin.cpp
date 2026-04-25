// Minimal plugin example for the DPL-Evolve V1 C ABI.
//
// It intentionally mirrors the built-in default behavior: if negotiation was
// requested by the Tcl command, run negotiation repair; otherwise run the
// diamond-compatible stage.

#include "EvolvePluginApi.h"

extern "C" int dpl_evolve_run_v1(const DplEvolveContextV1* context,
                                  const DplEvolveCallbacksV1* callbacks)
{
  callbacks->metric_int(callbacks->user_data, "dpl_evolve__plugin_example", 1);
  if (context->negotiation_requested) {
    callbacks->run_negotiation_repair(callbacks->user_data,
                                      context->abacus_requested);
  } else {
    callbacks->run_diamond_compatible(callbacks->user_data);
  }
  return 0;
}
