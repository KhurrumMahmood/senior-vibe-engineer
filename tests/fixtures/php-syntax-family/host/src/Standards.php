<?php

declare(strict_types=1);

function parseInvoice(): string
{
    return 'parsed';
}

function handledParse(): string
{
    try {
        return parseInvoice();
    } catch (RuntimeException) {
        return 'fallback';
    }
}

function unhandledParse(): string
{
    return parseInvoice();
}

$callStringDecoy = 'parseInvoice()';
