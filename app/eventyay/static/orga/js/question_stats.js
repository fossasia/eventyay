/** Draws the donut chart of responses on a custom field's page. */
const renderChart = () => {
    const serverData = document.getElementById("question-data")
    const canvas = document.getElementById("question-answers")
    // Fields without answers, file fields and fields with 50+ different answers have no chart.
    if (!serverData || !canvas) return
    const data = JSON.parse(serverData.dataset.states)
    let url = serverData.dataset.url
    const options = {
      series: data.map(e => e.count),
      labels: data.map(e => e.answer || e.options__answer),
      chart: {
        width: 420,
        type: 'donut',
        events: {
          dataPointSelection: (event, chartContext, config) => {
            // Reviewer fields have no list to filter, so like their table rows the slices aren't links.
            if (!url) return
            const clickedData = data[config.dataPointIndex]
            if (clickedData.answer) {
              url = url + "answer=" + encodeURIComponent(clickedData.answer)
            } else {
              url = url + "answer__options=" + encodeURIComponent(clickedData.options)
            }
            window.location.href = url
          },
          dataPointMouseEnter: () => {
            if (url) canvas.style.cursor = "pointer"
          },
          dataPointMouseLeave: () => {
            canvas.style.cursor = "inherit"
          },
        },
      },
      dataLabels: {
        enabled: false
      },
      legend: {
        formatter: function(val, opts) {
          if (val.length > 15) val = val.slice(0, 15) + "…"
          return val + " - " + opts.w.globals.series[opts.seriesIndex]
        },
        position: "bottom",
      },
      responsive: [{
        breakpoint: 480,
        options: {
          chart: {
            width: 200
          },
          legend: {
            position: 'bottom'
          }
        }
      }],
      plotOptions: {
        pie: {
          donut: {
            labels: {
              show: true,
              name: {
                formatter: (val) => {
                  if (val.length < 15) return val
                  return val.slice(0, 15) + "…"
                }
              }
            }
          }
        }
      },
      tooltip: {
        enabled: false
      }
    };

    let chart = new ApexCharts(document.querySelector("#question-answers"), options);
    chart.render();
}

onReady(() => renderChart())
