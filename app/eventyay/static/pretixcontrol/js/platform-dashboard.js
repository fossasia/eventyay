const dialog = document.querySelector('#platform-chart-dialog');
if (dialog) {
    const target = dialog.querySelector('[data-expanded-chart]');
    const title = dialog.querySelector('#platform-expanded-title');
    for (const button of document.querySelectorAll('[data-expand-chart]')) {
        button.addEventListener('click', () => {
            const chart = document.getElementById(button.dataset.expandChart);
            title.textContent = chart.querySelector('h3').textContent;
            target.dataset.chart = chart.dataset.chart;
            target.replaceChildren();
            for (const element of chart.children) {
                if (!element.matches('h3, .platform-chart-actions')) {
                    target.append(element.cloneNode(true));
                }
            }
            dialog.showModal();
        });
    }
}
