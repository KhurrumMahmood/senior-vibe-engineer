import SwiftA3Clean
import SwiftA3Core

precondition(activeTotal(4) == 8)
precondition(charge("id", audit: true) == 3)
precondition(CleanJob(state: .ready).state == .ready)
let download = Download()
precondition(!download.isActive())
download.start()
precondition(download.isActive())
download.finish()
precondition(!download.isActive())
print("swift-a3-checks-ok")
