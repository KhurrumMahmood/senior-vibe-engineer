#include "cppsemantic/semantic.hpp"

#include <iostream>

namespace cppsemantic::reports {
int alpha_report();
int beta_report();
int gamma_report();
}  // namespace cppsemantic::reports

int main()
{
    cppsemantic::Job job{};
    cppsemantic::queue(job);
    cppsemantic::finish(job);
    cppsemantic::start(job);
    const auto old_options = cppsemantic::options_straggler();
    const auto current_options = cppsemantic::options_alpha();
    const auto invoice = cppsemantic::summarize_invoice(100);
    const auto statement = cppsemantic::build_statement(100);
    (void)cppsemantic::options_beta();
    (void)cppsemantic::options_gamma();
    (void)cppsemantic::invoice_preview(100);
    (void)cppsemantic::statement_preview(100);
    (void)cppsemantic::migrate_status(cppsemantic::LegacyStatus::pending);
    (void)cppsemantic::overloaded(1);
    (void)cppsemantic::overloaded(1.0);
    (void)(cppsemantic::Score{1} + cppsemantic::Score{2});
    std::cout << "cpp-semantic:" << job.state << ':' << current_options.region << ':'
              << invoice.subtotal + statement.tax + old_options.retries
                     + current_options.retries
              << ':' << cppsemantic::invoke_registered(0) << ':'
              << cppsemantic::legacy_wire_name() << ':'
              << cppsemantic::reports::alpha_report()
                     + cppsemantic::reports::beta_report()
                     + cppsemantic::reports::gamma_report()
              << '\n';
    return 0;
}
