// app/static/js/common.js

/**
 * 체크박스 리스트(Slicer)를 생성하고 '전체' 선택 로직을 추가합니다.
 * @param {string} id - Slicer를 담을 div의 ID
 * @param {string[]} items - Slicer에 표시될 항목 배열
 * @param {boolean} checked - 초기 '전체' 체크 여부
 */
function populateSlicer(id, items, checked = true) {
  const container = document.getElementById(id);
  if (!container) return;

  // '전체' 옵션이 items에 없으면 추가
  const displayItems = items.includes('전체') ? items : ['전체', ...items]; //

  container.innerHTML = displayItems
    .map(
      (item) =>
        `<label><input type="checkbox" value="${item}" ${
          checked && item === '전체' ? 'checked' : ''
        }> ${item}</label>`
    )
    .join('');

  const allCheckbox = container.querySelector('input[value="전체"]');
  const otherCheckboxes = Array.from(
    container.querySelectorAll('input:not([value="전체"])')
  );

  container.addEventListener('change', (e) => {
    const target = e.target;
    if (target === allCheckbox && allCheckbox.checked) {
      otherCheckboxes.forEach((cb) => (cb.checked = false));
    } else if (otherCheckboxes.includes(target) && target.checked) {
      allCheckbox.checked = false;
    }

    if (otherCheckboxes.every((cb) => !cb.checked) && allCheckbox) {
      allCheckbox.checked = true;
    }
  });
}

/**
 * 드롭다운(Select) 메뉴를 생성합니다.
 * @param {string} id - Select 요소의 ID
 * @param {string[]} items - Option으로 표시될 항목 배열
 * @param {string} placeholder - 기본 안내 문구
 */
function populateSelect(id, items, placeholder) {
  const sel = document.getElementById(id);
  if (!sel) return;
  sel.innerHTML =
    `<option value="">${placeholder}</option>` +
    items.map((item) => `<option value="${item}">${item}</option>`).join('');
}

/**
 * 테이블 접기/펼치기 기능을 초기화합니다. (이벤트 위임 패턴 적용)
 * @param {string} tbodyId - 테이블의 tbody ID
 */
function initCollapse(tbodyId) {
  const tableBody = document.getElementById(tbodyId);
  if (!tableBody) return;

  tableBody.addEventListener('click', (event) => {
    const header = event.target.closest('.collapsible-header');
    if (!header) return;

    const groupId = header.dataset.groupId;
    header.classList.toggle('open');
    const isOpen = header.classList.contains('open');

    // 해당 그룹의 직계 자식만 토글
    tableBody
      .querySelectorAll(`tr[data-parent-id="${groupId}"]`)
      .forEach((childRow) => {
        childRow.classList.toggle('visible', isOpen);
        // 부모가 닫힐 때 하위 자식들도 숨김
        if (!isOpen) {
          childRow.classList.remove('open'); // 하위 헤더도 닫힘 상태로
          // 모든 하위 자식들도 숨김
          const childrenOfChild = tableBody.querySelectorAll(
            `tr[data-parent-id="${childRow.dataset.groupId}"]`
          );
          childrenOfChild.forEach((grandChild) => {
            grandChild.classList.remove('visible', 'open');
          });
        }
      });
  });
}

function showLoading(tableId) {
  document.getElementById('mainLoading').style.display = 'block';
  document.getElementById('mainError').style.display = 'none';
  document.getElementById(tableId).style.display = 'none';
}

function showTable(tableId) {
  document.getElementById('mainLoading').style.display = 'none';
  document.getElementById(tableId).style.display = 'table';
}

function handleError(message) {
  document.getElementById('mainLoading').style.display = 'none';
  const e = document.getElementById('mainError');
  if (e) {
    e.textContent = message;
    e.style.display = 'block';
  }
}
