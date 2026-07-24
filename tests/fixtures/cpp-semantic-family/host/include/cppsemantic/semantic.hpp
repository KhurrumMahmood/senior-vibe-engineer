#ifndef CPPSEMANTIC_SEMANTIC_HPP
#define CPPSEMANTIC_SEMANTIC_HPP

namespace cppsemantic {

struct Job {
    const char* state;
};

struct RequestOptions {
    const char* region;
    int retries;
};

struct Summary {
    int subtotal;
    int tax;
};

enum class CanonicalStatus {
    pending,
};

using LegacyStatus = CanonicalStatus;

void queue(Job& job);
void start(Job& job);
void finish(Job& job);
RequestOptions options_straggler();
RequestOptions options_alpha();
RequestOptions options_beta();
RequestOptions options_gamma();
Summary summarize_invoice(int cents);
Summary build_statement(int cents);
int invoice_preview(int cents);
int statement_preview(int cents);
int invoke_registered(int value);
CanonicalStatus migrate_status(LegacyStatus value);
const char* legacy_wire_name();

int overloaded(int value);
double overloaded(double value);

template <typename T>
T identity(T value)
{
    return value;
}

struct Score {
    int value;
};

Score operator+(Score left, Score right);

class AbstractScore {
public:
    virtual ~AbstractScore() = default;
    virtual int score() const = 0;
};

}  // namespace cppsemantic

#endif
