import SwiftA3Clean
import SwiftA3Core

precondition(activeTotal(4) == 8)
precondition(charge("id", audit: true) == 3)
precondition(CleanJob(state: .ready).state == .ready)
let job = Job()
precondition(!job.isRunning())
job.start()
precondition(job.isRunning())
job.finish()
precondition(!job.isRunning())
print("swift-a3-checks-ok")
