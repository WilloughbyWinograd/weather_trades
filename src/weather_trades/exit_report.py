"""Readable result and limitations for the historical selling-rule comparison."""


def build(summary, cfg, directory):
    def number(value):
        return "unavailable" if value is None else f"{value:+.2f}"

    def select(model, policy, phase="full", cohort="common"):
        return next(
            r
            for r in summary["results"]
            if r["model"] == model
            and r["policy"] == policy
            and r["phase"] == phase
            and r["cohort"] == cohort
        )

    lines = [
        "# Selling-rule comparison",
        "",
        "Holding to settlement had the highest average result for both models. Every tested selling rule lost money after fees on both the matched sample and each rule's available sample. Among timed sales, six hours was least negative for GFS and three hours was least negative for HRRR.",
        "",
        "Average net dollars per paper entry, including purchase and sale fees. Each entry has a maximum budget of $5; whole-contract sizing can leave part of that budget unused. The same tweet-method entries and forecast-publication evidence are retained.",
        "",
        "| Exit rule | GFS | HRRR |",
        "| --- | ---: | ---: |",
    ]
    for policy in cfg["policies"]:
        a, b = [select(model, policy["name"]) for model in cfg["models"]]
        lines.append(
            f"| {policy['name']} | {number(a['mean_net_profit'])} | {number(b['mean_net_profit'])} |"
        )
    counts = [select(model, cfg["policies"][0]["name"]) for model in cfg["models"]]
    complete_settlement = [
        select(model, "Settlement", cohort="all observed") for model in cfg["models"]
    ]
    lines += [
        "",
        "The table compares only entries with an observed exit under every rule: "
        + "; ".join(
            f"{r['model']} {r['priced_entries']} of {r['eligible_entries']} eligible entries"
            for r in counts
        )
        + ". This matches entries across exit rules but can favor markets with more complete quote records.",
        "",
        "Across every eligible entry, settlement averaged "
        + "; ".join(
            f"{r['model']} {number(r['mean_net_profit'])} dollars ({r['priced_entries']} entries)"
            for r in complete_settlement
        )
        + ". The stronger matched-sample GFS result therefore depends on excluding entries with missing selling quotes. This test does not establish a reliable profitable exit.",
        "",
        "## Earlier selection and later results",
        "",
        "Rules were selected using August 28–September 24 and then assessed on September 25–October 8. These dates had already been studied, so the later comparison is a stability check, not a new untouched evaluation.",
        "",
        "| Model | Selected on earlier dates | Earlier average | Later average | Later entries | Later 95 percent interval |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for choice in summary["earlier_selected_policies"]:
        a, b = choice["earlier"], choice["later"]
        low, high = b["mean_net_profit_95_percent_date_bootstrap"]
        lines.append(
            f"| {choice['model']} | {choice['selected_on_earlier_dates']} | {number(a['mean_net_profit'])} | {number(b['mean_net_profit'])} | {b['priced_entries']} | {number(low)} to {number(high)} |"
        )
    lines += [
        "",
        "Intervals resample target dates together to preserve dependence between cities on the same day. They are exploratory and do not adjust for choosing the best of seven rules.",
        "",
        "## Exit definitions",
        "",
        "- Timed exits use the first valid positive bid at or after the specified time, allowing up to 15 additional minutes. No earlier quote is carried forward.",
        "- Profit targets and stops compare the observed minute-close bid with the initial ask. Their thresholds are gross price changes, before fees. A trigger schedules a sale at the first valid quote at least one minute later, within the same 15-minute wait. Prices can move beyond the threshold before that quote.",
        "- Both target-and-stop rules have a six-hour time limit. Missing minute records can conceal threshold crossings; no unobserved intraminute trigger is assumed.",
        "- Settlement uses the verified $1 or $0 contract payout and has no sale or settlement fee.",
        "",
        "The [July 7, 2026 fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf) and the [recorded override audit](../fee-evidence.json) determine fees. A purchase and a sale both incur the standard taker fee. This comparison assumes quoted fills because historical order-book quantities are unavailable; it is not a cash-constrained portfolio or a live trading result.",
        "",
        "## Quote coverage and sensitivity",
        "",
        "The table below uses all observed exits for each rule. These samples differ, so compare them with the matched table above rather than ranking them alone.",
        "",
        "| Model | Exit rule | Observed / eligible | Unresolved | Average net dollars | Average holding minutes |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["results"]:
        if r["phase"] != "full" or r["cohort"] != "all observed":
            continue
        hold = (
            "unavailable"
            if r["mean_holding_minutes"] is None
            else f"{r['mean_holding_minutes']:.1f}"
        )
        lines.append(
            f"| {r['model']} | {r['policy']} | {r['priced_entries']}/{r['eligible_entries']} | {r['unresolved_exits']} | {number(r['mean_net_profit'])} | {hold} |"
        )
    lines += [
        "",
        "## Reproduction and evidence",
        "",
        "[Frozen rules](../../config/exit-comparison.json), [every policy outcome](ledger.csv), [all comparison groups](comparison.csv), [complete summary](summary.json), [source quotes and receipts](inputs.json), and [verification](verification.json). The [entry study](../tweet-price-response/summary.md) documents the Celsius-to-Fahrenheit adaptation, hourly polling, original run files, and one forecast comparison per day.",
        "",
        "Run `python -m weather_trades.cli replay-exits` to reproduce the calculation without network access. `compare-exits` reacquires public quote windows. `verify-exits` checks preserved responses, entry identity, chronology, independent fee arithmetic, and an identical replay with network connections disabled; it requires the local raw response cache.",
        "",
    ]
    (directory / "summary.md").write_text("\n".join(lines))
