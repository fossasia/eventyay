/* Dynamic fee / payout preview on the sell form. */

const form = document.getElementById("resale-sell-form")
if (form) {
    const priceInput = form.querySelector("#id_price")
    const feeEl = document.getElementById("resale-fee")
    const payoutEl = document.getElementById("resale-payout")
    const mode = form.dataset.feeMode || "fixed"
    const fixed = Number(form.dataset.feeFixed || "0")
    const percent = Number(form.dataset.feePercent || "0")
    const currency = form.dataset.currency || ""

    const formatMoney = (value) => {
        try {
            return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "EUR" }).format(value)
        } catch {
            return `${value.toFixed(2)} ${currency}`.trim()
        }
    }

    const refresh = () => {
        const price = Number(priceInput?.value || "0")
        if (!Number.isFinite(price) || price <= 0) return
        let fee = mode === "percent" ? (price * percent) / 100 : fixed
        fee = Math.min(fee, price)
        fee = Math.round(fee * 100) / 100
        const payout = Math.round((price - fee) * 100) / 100
        if (feeEl) feeEl.textContent = formatMoney(fee)
        if (payoutEl) payoutEl.innerHTML = `<strong>${formatMoney(payout)}</strong>`
    }

    priceInput?.addEventListener("input", refresh)
    refresh()
}
