Handlebars.registerHelper('numberWithCommas', function (str) {
	return numberWithCommas(str);
});
Handlebars.registerHelper('parseFloat', function (str) {
	return parseFloat(str).toFixed(2);
});
Handlebars.registerHelper('ifCond', function (v1, operator, v2, options) {
	switch (operator) {
		case '==': return (v1 == v2) ? options.fn(this) : options.inverse(this);
		case '===': return (v1 === v2) ? options.fn(this) : options.inverse(this);
		case '!=': return (v1 != v2) ? options.fn(this) : options.inverse(this);
		case '>': return (v1 > v2) ? options.fn(this) : options.inverse(this);
		case '<': return (v1 < v2) ? options.fn(this) : options.inverse(this);
		case '>=': return (v1 >= v2) ? options.fn(this) : options.inverse(this);
		case '<=': return (v1 <= v2) ? options.fn(this) : options.inverse(this);
		default: return options.inverse(this);
	}
});
Handlebars.registerHelper('contains', function(str, substr, options) {
	if (typeof str === 'string' && str.includes(substr)) {
		return options.fn(this); // 조건 만족할 때 실행할 블록
	} else {
		return options.inverse(this); // 조건 만족하지 않을 때 실행할 블록
	}
});
Handlebars.registerHelper('toPercent', function(value) {
	return (value * 100).toFixed(2);
});
Handlebars.registerHelper('toFixed', function(value) {
	try {
		
		const num = parseFloat(value);
		
		if (isNaN(num)) return 0;
		return num.toFixed(2);
	} catch (e) {
		return 0;
	}
});

Handlebars.registerHelper('toFixed1', function (value) {
	try {
		const num = parseFloat(value);
		if (isNaN(num)) return '0.0';

		// 소수점 1자리 고정
		const fixed = num.toFixed(1); // 예: "1234.5"

		// 정수부/소수부 분리
		const parts = fixed.split('.');
		let intPart = parts[0];
		const decPart = parts[1] ?? '0';

		// 정수부 3자리마다 콤마
		intPart = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');

		return intPart + '.' + decPart; // 예: "1,234.5"
	} catch (e) {
		return '0.0';
	}
});


Handlebars.registerHelper('contains2', function(str, substr) {
	return typeof str === 'string' && str.includes(substr);
});
Handlebars.registerHelper('joinWithComma', function(arr) {
	return Array.isArray(arr) ? arr.join(',') : '';
});

Handlebars.registerHelper('joinWithNewline', function(arr) {
	return Array.isArray(arr) ? arr.join('\n') : '';
});
Handlebars.registerHelper('length', function(arr) {
	return Array.isArray(arr) ? arr.length : 0;
});
$.datepicker.setDefaults({
	dateFormat: "yy-mm-dd"
});
Handlebars.registerHelper('truncate', (str, n) => (typeof str === 'string' ? (str.length > n ? str.slice(0, n) : str) : ''));

Handlebars.registerHelper('rowOpen', (i) => i % 2 === 0);
Handlebars.registerHelper('rowClose', (i, last) => (i % 2 === 1) || last);

Handlebars.registerHelper('textOr', (v, alt) => {
	if (v == null) return alt; // null/undefined
	if (typeof v === 'string' && v.trim() === '') return alt; // 공백만
	return v; // 0 같은 값은 그대로 출력
});

Handlebars.registerHelper('inc', v => parseInt(v, 10) + 1);

Handlebars.registerHelper('lt', function(a, b, options) {
	return (a < b) ? options.fn(this) : options.inverse(this);
});
Handlebars.registerHelper('eq', function(a, b, options) {
	return (a === b) ? options.fn(this) : options.inverse(this);
});

//공통 포맷 함수 (헬퍼 안에서만 사용)
function summarizeCount(n) {
	if (n == null || isNaN(n)) return '';

	n = Number(n);

	// 0 ~ 1만 미만은 구간으로
	if (n < 100) return '~100';
	if (n < 200) return '100~200';
	if (n < 500) return '200~500';
	if (n < 1000) return '500~1,000';
	if (n < 1500) return '1,000~1,500';

	if (n < 10000) {
		// 1,500 이상 ~ 10,000 미만 → 500 단위 올림 + "이상"
		const unit = 500;
		const rounded = Math.ceil(n / unit) * unit;
		return rounded.toLocaleString() + '~';
	}

	// 1만 이상 → "9.8만" 형태
	const man = n / 10000;
	let v = man.toFixed(1);		// 5.8466 → "5.8"
	v = v.replace(/\.0$/, '');	// 정수면 소수점 제거

	return v + '만';
}

// 1) qc용 헬퍼
Handlebars.registerHelper('qcSummary', function (qc) {
	return summarizeCount(qc);
});

// 2) pv용 헬퍼
Handlebars.registerHelper('pvSummary', function (pv) {
	return summarizeCount(pv);
});
$.datepicker.setDefaults($.datepicker.regional["ko"]);



Handlebars.registerHelper('getSortText', function (sortType) {
	if(sortType == 'pv')
		return '클릭순';
	else if(sortType == 'ctr')
		return '클릭율순';
	else if(sortType == 'ad')
		return '광고비중순';
	else if(sortType == 'sales')
		return '매출순';
	else
		return '???';
});


Handlebars.registerHelper('eachLimit', function (arr, limit, options) {
	if (!Array.isArray(arr)) return '';
	let out = '';
	for (let i = 0; i < arr.length && i < limit; i++) {
		out += options.fn(arr[i]);
	}
	return out;
});
Handlebars.registerHelper('chunk', function (array, size, options) {
	let result = '';
	for (let i = 0; i < array.length; i += size) {
		result += options.fn(array.slice(i, i + size));
	}
	return result;
});
