// app/static/js/dashboard_item.js

let pieChartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
  initCollapse('itemTableBody');
  initFilters();
});

function initFilters() {
  // [중요] URL에 currentBrand 적용
  fetch(`/api/${currentBrand}/filters`)
    .then((res) => res.json())
    .then((data) => {
      populateSlicer('warehouse-filter', ['전체', ...data.warehouses], true);
      populateSlicer('category-filter', ['전체', ...data.categories], true);
      populateSelect('main-year', data.years, '집계년도 선택');
      populateSelect('start-month', data.months, '시작월');
      populateSelect('end-month', data.months, '종료월');
      addEventListenersToFilters();
      fetchAndRender();
    })
    .catch((err) => handleError(err, 'itemReportTable'));
}

function addEventListenersToFilters() {
  document
    .getElementById('apply-filters')
    .addEventListener('click', fetchAndRender);

  document.getElementById('reset-filters').addEventListener('click', () => {
    window.location.reload();
  });

  document
    .getElementById('item-search')
    .addEventListener('input', applyLiveSearch);
}

function fetchAndRender() {
  showLoading('itemReportTable');
  const qs = buildQueryString();
  // [중요] URL에 currentBrand 적용
  fetch(`/api/${currentBrand}/data/item?${qs}`)
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      return res.json();
    })
    .then((resp) => {
      if (resp.error) return handleError(resp.error, 'itemReportTable');
      buildTable(resp.months, resp.rows);
      renderChartAndRank(resp.top_series_data);
      showTable('itemReportTable');
    })
    .catch((err) =>
      handleError('데이터 로드 중 오류 발생: ' + err.message, 'itemReportTable')
    );
}

function buildQueryString() {
  const params = new URLSearchParams();
  const getCheckedValues = (selector) =>
    Array.from(document.querySelectorAll(`${selector} input:checked`))
      .filter((input) => input.value !== '전체')
      .map((input) => input.value);
  getCheckedValues('#warehouse-filter').forEach((w) =>
    params.append('warehouse', w)
  );
  getCheckedValues('#category-filter').forEach((c) =>
    params.append('category', c)
  );
  params.append('main_year', document.getElementById('main-year').value);
  params.append('start_month', document.getElementById('start-month').value);
  params.append('end_month', document.getElementById('end-month').value);
  return params.toString();
}

function buildTable(months, rows) {
  const hdr = document.getElementById('tableHeader');
  const bdy = document.getElementById('itemTableBody');
  hdr.innerHTML = '';
  bdy.innerHTML = '';
  const mainYear = document.getElementById('main-year').value || '----';

  // [총 합계 헤더 위치 이동]
  const headerHTML = `<tr>
    <th>구분 / 시리즈 / 품목</th>
    <th colspan="2" class="total-header">총 합계 ${mainYear}</th>
    ${months.map((m) => `<th colspan="2">${m}</th>`).join('')}
  </tr>`;

  hdr.innerHTML = headerHTML;
  bdy.innerHTML = rows.map((row) => buildRowRecursive(row, months)).join('');
}

function buildRowRecursive(row, months) {
  let html = '';
  const isItemRow = row.level === 3;
  const isSubtotalRow = row.level === 0;
  let rowClass = `level-${row.level}`;
  if (!isItemRow && !isSubtotalRow) rowClass += ' collapsible-header';
  const parentAttr = row.parentId ? `data-parent-id="${row.parentId}"` : '';
  html += `<tr class="${rowClass}" data-group-id="${row.id}" ${parentAttr}>`;
  let nameCell = `<td>${row.name}`;
  if (isItemRow) {
    nameCell += `<span class="stock-quantity">[${row.stock}]</span>`;
  }
  nameCell += '</td>';
  html += nameCell;

  // [총 합계 셀 위치 이동]
  const total = row.total;
  html += `<td class="total-cell">${total.net.toLocaleString()}</td><td class="total-cell negative">${total.neg.toLocaleString()}</td>`;

  months.forEach((m) => {
    const d = row.data[m] || { net: 0, neg: 0 };
    let netCellClass = '';
    let negCellClass = 'negative';
    if (row.level >= 2) {
      if (d.net >= 100) netCellClass = 'highlight-bold';
      if (d.neg <= -60) negCellClass += ' highlight-bold';
    }
    html += `<td class="${netCellClass}">${d.net.toLocaleString()}</td><td class="${negCellClass}">${d.neg.toLocaleString()}</td>`;
  });

  html += `</tr>`;
  if (row.children && row.children.length > 0) {
    row.children.forEach((child) => (html += buildRowRecursive(child, months)));
  }
  return html;
}

function renderChartAndRank(seriesData) {
  const chartCtx = document.getElementById('seriesPieChart').getContext('2d');
  const rankList = document.getElementById('seriesRankList');
  if (!rankList || !chartCtx) return;
  rankList.innerHTML = '';
  if (pieChartInstance) pieChartInstance.destroy();
  if (!seriesData || seriesData.length === 0) {
    chartCtx.clearRect(0, 0, chartCtx.canvas.width, chartCtx.canvas.height);
    return;
  }
  const labels = seriesData.map((d) => d.series);
  const data = seriesData.map((d) => d.quantity);
  const chartColors = [
    '#3498db',
    '#e74c3c',
    '#2ecc71',
    '#f1c40f',
    '#9b59b6',
    '#34495e',
    '#1abc9c',
    '#e67e22',
    '#7f8c8d',
    '#d35400',
  ];
  const listHtml = seriesData
    .map(
      (d, index) =>
        `<li data-series-name="${d.series}">
            <span class="color-swatch" style="background-color: ${
              chartColors[index % chartColors.length]
            };"></span>
            <span class="rank-number">${index + 1}.</span>
            ${d.series}
        </li>`
    )
    .join('');
  rankList.innerHTML = `<ol>${listHtml}</ol>`;
  pieChartInstance = new Chart(chartCtx, {
    type: 'pie',
    data: {
      labels: labels,
      datasets: [
        {
          label: '시리즈별 판매량',
          data: data,
          backgroundColor: chartColors,
          hoverOffset: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: '시리즈별 판매량 Top 10 (케이스 제외)' },
      },
      onClick: (event, elements) => {
        if (elements.length > 0)
          handleSeriesClick(pieChartInstance.data.labels[elements[0].index]);
      },
    },
  });
  rankList.addEventListener('click', (e) => {
    const li = e.target.closest('li');
    if (li && li.dataset.seriesName) handleSeriesClick(li.dataset.seriesName);
  });
}

function handleSeriesClick(seriesName) {
  const searchInput = document.getElementById('item-search');
  searchInput.value = seriesName;
  searchInput.dispatchEvent(new Event('input', { bubbles: true }));
}

function applyLiveSearch(event) {
  const searchTerm = event.target.value.toLowerCase();
  const tbody = document.getElementById('itemTableBody');
  if (!tbody) return;
  const allTrs = Array.from(tbody.querySelectorAll('tr'));
  if (!searchTerm) {
    allTrs.forEach((tr) => {
      tr.style.display = '';
      const isChild = tr.dataset.parentId;
      if (isChild) {
        const header = tbody.querySelector(
          `[data-group-id="${tr.dataset.parentId}"]`
        );
        if (!header || !header.classList.contains('open')) {
          tr.classList.remove('visible');
          tr.style.display = 'none';
        }
      }
    });
    return;
  }
  const visibleRows = new Set();
  allTrs.forEach((tr) => {
    if (tr.classList.contains('level-3')) {
      const itemName = tr
        .querySelector('td:first-child')
        .textContent.toLowerCase();
      if (itemName.includes(searchTerm)) {
        visibleRows.add(tr.dataset.groupId);
        let parentId = tr.dataset.parentId;
        while (parentId) {
          visibleRows.add(parentId);
          const parentRow = tbody.querySelector(
            `[data-group-id="${parentId}"]`
          );
          parentId = parentRow ? parentRow.dataset.parentId : null;
        }
      }
    }
  });
  allTrs.forEach((tr) => {
    const groupId = tr.dataset.groupId;
    tr.style.display =
      tr.classList.contains('level-0') || visibleRows.has(groupId)
        ? 'table-row'
        : 'none';
  });
}
