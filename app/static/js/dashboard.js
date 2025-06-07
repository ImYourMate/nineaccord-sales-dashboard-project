// app/static/js/dashboard.js

// 전역 변수들은 그대로 둡니다.
let allWarehouses = [];
let allCategories = [];
let allYears = [];
let allMonths = [];
let chartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
  // --- 수정: 접기/펼치기 기능을 페이지 로드 시 단 한 번만 초기화 ---
  initCollapse('mainTableBody');
  initFilters();
});

function initFilters() {
  fetch('/api/filters')
    .then((res) => res.json())
    .then((data) => {
      // 전역 변수에 데이터 할당
      allWarehouses = data.warehouses;
      allCategories = data.categories;
      allYears = data.years;
      allMonths = data.months;

      populateSlicer('warehouse-filter', ['전체', ...allWarehouses], true);
      populateSlicer('category-filter', ['전체', ...allCategories], true);
      populateSelect('main-year', allYears, '집계년도 선택');
      populateSelect('comp-year', allYears, '비교년도 없음');
      populateSelect('start-month', allMonths, '시작월');
      populateSelect('end-month', allMonths, '종료월');

      addEventListenersToFilters();
      fetchAndRender();
    })
    .catch((err) => handleError(err, 'mainReportTable'));
}

function addEventListenersToFilters() {
  document
    .getElementById('apply-filters')
    .addEventListener('click', fetchAndRender);

  // --- 수정: '전체 초기화' 버튼의 동작을 페이지 새로고침으로 변경 ---
  document.getElementById('reset-filters').addEventListener('click', () => {
    window.location.reload();
  });
}

// --- resetAllFilters 함수는 이제 필요 없으므로 삭제합니다. ---

function fetchAndRender() {
  showLoading('mainReportTable');
  const qs = buildQueryString();
  fetch(`/api/data?${qs}`) // API 경로 확인
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      return res.json();
    })
    .then((resp) => {
      if (resp.error) return handleError(resp.error, 'mainReportTable');
      buildTable(resp.months, resp.rows);
      renderChart(resp.months, resp.rows);
      showTable('mainReportTable');
    })
    .catch((err) =>
      handleError('데이터 로드 중 오류 발생: ' + err.message, 'mainReportTable')
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
  params.append('comp_year', document.getElementById('comp-year').value);
  params.append('start_month', document.getElementById('start-month').value);
  params.append('end_month', document.getElementById('end-month').value);
  return params.toString();
}

function buildTable(months, rows) {
  const hdr = document.getElementById('tableHeader');
  const bdy = document.getElementById('mainTableBody');
  hdr.innerHTML = '';
  bdy.innerHTML = '';

  const mainYear = document.getElementById('main-year').value || '----';
  const compYear = document.getElementById('comp-year').value || '----';
  const hasCompare =
    document.getElementById('comp-year').value &&
    rows.some(
      (r) =>
        'compare' in r ||
        (r.categories && r.categories.some((c) => 'compare' in c))
    );

  const headerRow = `<tr>
    <th>창고 / 구분</th>
    ${months.map((m) => `<th colspan="2">${m}</th>`).join('')}
    <th colspan="2" class="total-header">총 합계 ${mainYear}</th>
    ${
      hasCompare
        ? `<th colspan="2" class="total-header">비교 합계 ${compYear}</th><th>증감률(%)</th>`
        : ''
    }
    </tr>`;
  hdr.innerHTML = headerRow;
  bdy.innerHTML = rows.map((r) => buildRow(r, months, hasCompare)).join('');
  // initCollapse 호출을 여기서 제거했습니다.
}

function buildRow(row, months, hasCompare) {
  let html = '';
  const isWarehouse = row.is_header;
  const isSubtotal = row.is_subtotal;
  let rowClass = '';
  let attrs = '';

  if (isWarehouse) {
    rowClass = 'warehouse-row collapsible-header';
    attrs = `data-group-id="${row.name}"`;
  } else if (isSubtotal) {
    rowClass = 'subtotal-row';
  } else {
    rowClass = 'category-row';
    attrs = `data-parent-id="${row.parentId}"`;
  }

  html += `<tr class="${rowClass}" ${attrs}><td>${row.name}</td>`;

  months.forEach((m) => {
    const d = row.data[m] || { net: 0, neg: 0 };
    html += `<td>${d.net.toLocaleString()}</td><td class="negative">${d.neg.toLocaleString()}</td>`;
  });

  const t = row.total || { net: 0, neg: 0 };
  html += `<td class="total-cell">${t.net.toLocaleString()}</td><td class="total-cell negative">${t.neg.toLocaleString()}</td>`;

  if (hasCompare) {
    const c = row.compare || { net: 0, neg: 0 };
    const pct = row.pct_change;
    const pctClass =
      pct != null ? (pct > 0 ? 'pct-positive' : 'pct-negative') : '';
    html += `<td class="total-cell">${c.net.toLocaleString()}</td><td class="total-cell negative">${c.neg.toLocaleString()}</td>`;
    html += `<td class="total-cell ${pctClass}">${
      pct != null ? `${pct > 0 ? '+' : ''}${pct}%` : '-'
    }</td>`;
  }
  html += `</tr>`;

  if (row.categories && row.categories.length > 0) {
    html += row.categories
      .map((cat) => buildRow(cat, months, hasCompare))
      .join('');
  }
  return html;
}

function renderChart(months, rows) {
  if (chartInstance) chartInstance.destroy();
  const colorMap = {
    안경원: '#e6194B',
    면세: '#f58231',
    수출: '#3cb44b',
    케이스: '#808080',
  };
  const otherColors = [
    '#4363d8',
    '#ffe119',
    '#911eb4',
    '#46f0f0',
    '#9A6324',
    '#000075',
  ];
  let otherColorIndex = 0;

  const datasets = rows
    .filter((r) => r.is_header && r.name !== '케이스')
    .map((wh) => {
      let color =
        colorMap[wh.name] ||
        otherColors[otherColorIndex++ % otherColors.length];
      return {
        label: wh.name,
        data: months.map((m) => (wh.data[m] ? wh.data[m].net : 0)),
        backgroundColor: color,
      };
    });

  chartInstance = new Chart(
    document.getElementById('barChart').getContext('2d'),
    {
      type: 'bar',
      data: { labels: months, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          title: { display: true, text: '월별 창고 판매 현황' },
        },
      },
    }
  );
}
