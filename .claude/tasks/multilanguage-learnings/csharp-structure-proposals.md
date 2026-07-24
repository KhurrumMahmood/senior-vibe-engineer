# C# accepted structure-proposal learning

- Keep structure detection, subsystem mapping, and proposal rendering separate:
  the proposal consumer validates final producer/map/fact artifacts and never
  invokes a detector or map producer.
- Bind human acceptance to the exact producer, integrated map, Roslyn fact pack,
  project/config/source hashes, selected skill/helper/provider bytes, pinned
  SDK/Roslyn authority, one candidate, and a closed boundary-verdict map.
- Boundary extraction must preserve exact compatibility shims and cite resolved
  callers; folder movement must preserve namespace/type/assembly identity and
  carry exact manifest and explicit project compile-item after-states.
- Prove both proposals by applying their exact scope in a disposable copy and
  running build, native test, and executable smoke. Run the current-tree proof
  in a disposable copy too because MSBuild restore/build artifacts are not
  read-only host output.
- On macOS, the bounded fixture sets `UseAppHost=false` so `dotnet run` uses the
  pinned dotnet host and built DLL; this avoids an environment-specific native
  apphost kill while still exercising the executable output boundary.
- Replace success/refusal/recovery output directories as whole terminal bundles;
  source mutation remains a separate human decision.
