$.ajaxSetup({
	beforeSend: function(xhr){
		xhr.setRequestHeader("X-ajax-call", true);
	},
	complete: function(data){
		if(data.status == 401){
			alert('로그인이 필요합니다.');
		}
	}
});
function escapeRegExp(str) {
	return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // $& means the whole matched string
}

function replaceAll(str, find, replace) {
    return str.replace(new RegExp(escapeRegExp(find), 'g'), replace);
}


$(function(){
	$('.btnShowCoupon').click(function(){
		$('.cpncode').show();
	})


	$(".allownumericwithdecimal").on("keypress keyup blur",function (event) {
		 //this.value = this.value.replace(/[^0-9\.]/g,'');
		 $(this).val($(this).val().replace(/[^0-9\.]/g,''));
		 if ((event.which != 46 || $(this).val().indexOf('.') != -1) && (event.which < 48 || event.which > 57)) {
			 event.preventDefault();
		 }
	});
	$(".allownumericwithoutdecimal").on("keypress keyup blur",function (event) {    
		 $(this).val($(this).val().replace(/[^\d].+/, ""));
		 if ((event.which < 48 || event.which > 57)) {
			 event.preventDefault();
		 }
	 });
	

});

function numberWithCommas(x) {
	if(!x)
		return '0';
	else
		return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function getAgoDate(yyyy, mm, dd){
	var today = new Date();
	var year = today.getFullYear();
	var month = today.getMonth();
	var day = today.getDate();
 
	var resultDate = new Date(yyyy+year, month+mm, day+dd);
 
 
	year = resultDate.getFullYear();
	month = resultDate.getMonth() + 1;
	day = resultDate.getDate();

	if (month < 10)
		month = "0" + month;
	if (day < 10)
		day = "0" + day;
	return year + "-" + month + "-" + day;
}

$(document).on('focus', '.numberBox', function(){
	var val = $(this).val();
	val = val.replaceAll(',', '');
	$(this).val(val);
});

$(document).on('blur', '.numberBox', function(){
	var $this = $(this);
	
	var val = $this.val();
	
	val = val.replace(/[^0-9]/g,"");
	
	val = numberWithCommas(val);
	$this.val(val);
});

$(document).on('keyup', '.onlyNumber', function(){
	$(this).val($(this).val().replace(/[^0-9.]/g,""));			
});

function convertToJsonData(formId){
	var data = $('#' + formId).serializeArray();
	
	var object = {};
	
	
	for (var i = 0; i < data.length; i++){
	    object[data[i]['name']] = data[i]['value'];
	}
	
	
	var json = JSON.stringify(object);
	
	return json;
}


function convertToJsonObject(formId){
	var data = $('#' + formId).serializeArray();
	
	var object = {};
	
	
	for (var i = 0; i < data.length; i++){
	    object[data[i]['name']] = data[i]['value'];
	}
	
	return object;
}

function convertToJsonObject2(formObj){
	var data = $(formObj).serializeArray();
//	console.log(data)
	var object = {};
	
	
	for (var i = 0; i < data.length; i++){
	    object[data[i]['name']] = data[i]['value'];
	}
	
	return object;
}

function getLengthStr(txt, len) {
	
	if(txt.length > len)
		txt = txt.substring(0, len) + "...";
	

	txt = txt.replace("<b>", "");
	txt = txt.replace("</b>", "");
	txt = txt.replace("<strong>", "");
	txt = txt.replace("</strong>", "");
	
	txt = txt.replace("<", "&lt;");    	
//	data = data.replaceAll("'", "&apos;");    	
	txt = txt.replace(">", "&gt;");
	
	
	return txt;
}

function highlightFromObjects(inputString, objects, fieldName) {
	
	
	
    if (!inputString || typeof inputString !== 'string') {
    	return inputString;
//        throw new Error('첫 번째 매개변수는 문자열이어야 합니다.');
    }

    if (!Array.isArray(objects)) {
    	
        throw new Error('두 번째 매개변수는 객체 배열이어야 합니다.');
    }

    if (!fieldName) {
        throw new Error('세 번째 매개변수는 필드 이름이어야 합니다.');
    }

    // 객체 배열에서 필드 값을 추출하여 정규식으로 만듦
    const targetStrings = objects
        .map(obj => obj[fieldName])
        .filter(value => typeof value === 'string'); // 문자열만 포함

    if (targetStrings.length === 0) {
        return inputString; // 강조할 대상이 없으면 원본 문자열 반환
    }

    const regex = new RegExp(targetStrings.map(escapeRegExp).join('|'), 'gi');

    // 강조 처리
    const highlighted = inputString.replace(
        regex,
        match => `<span style="color: red;">${match}</span>`
    );

    return highlighted;
}


// 정규식에서 특수문자 처리를 위한 함수
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // 정규식 특수문자 이스케이프
}

function isChromeBrowser() {
	if (navigator.userAgentData?.brands) {
		return navigator.userAgentData.brands.some(b =>
			b.brand.includes("Chromium") || b.brand.includes("Google Chrome")
		);
	} else {
		const ua = navigator.userAgent;
		return ua.includes("Chrome") && !ua.includes("Edg") && !ua.includes("OPR");
	}
}


function isHelpstoreExtensionInstalled(timeout = 2000) {
	return new Promise((resolve) => {
		let resolved = false;

		const listener = (event) => {
			if (event.data?.type === "HELPSTORE_PONG") {
				resolved = true;
				window.removeEventListener("message", listener);
				resolve(true); // ✅ 설치됨
			}
		};

		window.addEventListener("message", listener);

		// 1. ping 보내기
		window.postMessage({ type: "HELPSTORE_PING" }, "*");

		// 2. timeout 안에 응답 없으면 false 처리
		setTimeout(() => {
			if (!resolved) {
				window.removeEventListener("message", listener);
				resolve(false); // ❌ 미설치
			}
		}, timeout);
	});
}

function extensionCheck(){
	// 사용 예시
	isHelpstoreExtensionInstalled().then((installed) => {
		if (!installed) {
			const currentUrl = location.pathname + location.search + location.hash;
			location.href = '/extension/page?url=' + currentUrl;
		}
	});
	
	
}


function parseShoppingResult(json) {
	const result = {};
	const productList = new Array();

	const props = json.props;
	const pageProps = props.pageProps;
	const compositeList = pageProps.compositeList;
	const products = compositeList.list;
    
//    let partialSearched = false;        //일치검색 여부
//    if(pageProps.partialSearched)
//        partialSearched = pageProps.partialSearched;
//    result.partialSearched = partialSearched;

	let ranking = 1;
	let rankingIncludeAd = 1;
	let priceCount = 0;
	
	products.forEach(productItem => {
		let foundProduct = {};
		let product = productItem.item;

		let shopLink = '';
		if (product.mallProductUrl) {   
			shopLink = product.mallProductUrl;
		} else if (product.productUrl) {
			shopLink = product.productUrl;
		} else {
			shopLink = '';
		}
		foundProduct.link = shopLink;

		if(product.hasOwnProperty("adId"))
			foundProduct.adId = product.adId;
		
		foundProduct.scoreInfo = product.scoreInfo;
		foundProduct.openDate = product.openDate;
		
		
		foundProduct.category1Id = product.category1Id;
		foundProduct.category2Id = product.category2Id;
		foundProduct.category3Id = product.category3Id;
		foundProduct.category4Id = product.category4Id;
		
		foundProduct.category1Name = product.category1Name;
		foundProduct.category2Name = product.category2Name;
		foundProduct.category3Name = product.category3Name;
		foundProduct.category4Name = product.category4Name;
		
		let categoryString = "";

		if (product.category1Name)
			categoryString += ">" + product.category1Name;
		if (product.category2Name)
			categoryString += ">" + product.category2Name;
		if (product.category3Name)
			categoryString += ">" + product.category3Name;
		if (product.category4Name)
			categoryString += ">" + product.category4Name;

		if (categoryString.startsWith(">"))
			categoryString = categoryString.substring(1).trim();

		if (categoryString.endsWith(">"))
			categoryString = categoryString.substring(0, categoryString.lastIndexOf(">")).trim();
		
		foundProduct.categoryName = categoryString;
		foundProduct.price = product.price;
		
		if (product?.mallInfoCache?.mallGrade) {
			const mallGrade = String(product.mallInfoCache.mallGrade);

			const gradeMap = {
				"M44004": "파워",
				"M44003": "빅파워",
				"M44002": "프리미엄",
				"M44005": "굿서비스",
				"M44001": "플래티넘"
			};

			foundProduct.mallGrade = gradeMap[mallGrade] || "";
		}else{
			foundProduct.mallGrade = "";
		}

		
		let mallCount = 0;
		if(product.mallCount)
			mallCount = product.mallCount;
		foundProduct.mallCount = mallCount;

		if(mallCount > 0 && product.lowMallList){
			let shopList = product.lowMallList;
			let mallList = new Array();

			for (const shop of shopList) {
				if(shop.name){
					let mallName = shop.name.replace(" ", "");
					mallList.push(mallName);
				}else{
					mallList.push("UNKNOWN");
				}
			}
			foundProduct.mallList = mallList;
			foundProduct.isPriceProduct = true;
			priceCount++;
		}else{
			let mallName = '';
			if(product.mallName){
				mallName = product.mallName.replace(" ", "");
				foundProduct.mallName = mallName;
			}else{
				foundProduct.mallName = "UNKNOWN";
			}
			foundProduct.isPriceProduct = false;
		}

			
		let title = "";
		if(product.productTitle)
			title = product.productTitle;
		else
			title = product.productName;
		foundProduct.title = title;

		let nvMid = "";		
		if(product.id)
			nvMid = product.id;
		else
			nvMid = product.nvMid;
		foundProduct.nvMid = nvMid;
		
		let mallPid = "";
		if(product.mallProductId)
			mallPid = product.mallProductId;
		foundProduct.mallPid = mallPid;

		let img = "";
		if(product.imageUrl)
			img = product.imageUrl;
		else
			img = product.productImgUrl;
		foundProduct.img = img;

		let productDate = "";
		if(product.openDate)
			productDate = product.openDate;						
		if (productDate.length > 8) productDate = productDate.substring(0, 8);
		foundProduct.productDate = productDate;

		
		if(foundProduct.isPriceProduct)
			foundProduct.link = 'https://search.shopping.naver.com/catalog/' + nvMid;
		
		let reviewCount = -1;
		if(product.reviewCount)
			reviewCount = product.reviewCount;			
		foundProduct.reviewCount = reviewCount;

		let purchaseCount = -1;
		if(product.purchaseCnt)
			purchaseCount = product.purchaseCnt;
		foundProduct.purchaseCount = purchaseCount;

		let keepCount = -1;
		if(product.keepCnt)
			keepCount = product.keepCnt;						
		foundProduct.keepCount = keepCount;
		
		let rankingType = "";
		let searchResultType = "";
		let isHotDeal = product.isHotDeal;
		if(isHotDeal == 1){
			rankingType = "H";
			searchResultType = "핫";
		}else if(mallCount > 0){
			rankingType = "L";
			searchResultType = "가";
		}else{
			if (shopLink.indexOf("smartstore.naver.com") > -1){
				rankingType = "N";
				searchResultType = "스";
			}else if (shopLink.indexOf("shopping.naver.com/style") > -1
					|| shopLink.indexOf("shopping.naver.com/department") > -1
					|| shopLink.indexOf("shopping.naver.com/outlet") > -1
					|| shopLink.indexOf("shopping.naver.com/beauty") > -1
					|| shopLink.indexOf("shopping.naver.com/living") > -1
					|| shopLink.indexOf("shopping.naver.com/fresh") > -1
					|| shopLink.indexOf("shopping.naver.com/art") > -1)
			{
				rankingType = "W";
				searchResultType = "윈";
			}else{
				rankingType = "I";
				searchResultType = "자";
			}
		}
		foundProduct.rankingType = rankingType;
		foundProduct.searchResultType = searchResultType;
		
		foundProduct.ranking = ranking;
		foundProduct.rankingIncludeAd = rankingIncludeAd;

		if(product.adId){
			foundProduct.isAd = true;
		}else{
			foundProduct.isAd = false;
			ranking++;
		}
		rankingIncludeAd++;

		productList.push(foundProduct);
	});
	
	
	//여기부터
	(() => {
		const productListRaw = productList;
		if (!Array.isArray(productListRaw)) return;

		const filteredList = productListRaw.filter(p => p.isAd === false);

		const knownList = filteredList.filter(p => typeof p.purchaseCount === 'number' && p.purchaseCount >= 0);
		const unknownList = filteredList.filter(
			p => (typeof p.purchaseCount !== 'number' || p.purchaseCount < 0) && p.isPriceProduct !== true
		);

		const sortedKnown = [...knownList].sort((a, b) => a.rankingIncludeAd - b.rankingIncludeAd);
		const rankArr = sortedKnown.map(p => p.rankingIncludeAd);
		const countArr = sortedKnown.map(p => p.purchaseCount);

		const estimateCount = (rank) => {
			if (rankArr.length === 0) return 0;
			if (rank <= rankArr[0]) return countArr[0];
			if (rank >= rankArr[rankArr.length - 1]) return countArr[countArr.length - 1];
			for (let i = 0; i < rankArr.length - 1; i++) {
				const r1 = rankArr[i], r2 = rankArr[i + 1];
				const c1 = countArr[i], c2 = countArr[i + 1];
				if (rank >= r1 && rank <= r2) {
					const ratio = (rank - r1) / (r2 - r1);
					return Math.round(c1 + (c2 - c1) * ratio);
				}
			}
			return 0;
		};

		// ✅ purchaseCount는 절대 건드리지 않고, 계산용 별도 필드 사용
		knownList.forEach(p => {
			p.purchaseCountCalc = p.purchaseCount; // 실제값 그대로
		});
		unknownList.forEach(p => {
			p.purchaseCountCalc = estimateCount(p.rankingIncludeAd); // 추정값
		});

		const finalProducts = [...knownList, ...unknownList];

		let sumSales = 0;
		let sumPurchase = 0;

		finalProducts.forEach(p => {
			const price = parseInt(p.price, 10);
			const cnt = typeof p.purchaseCountCalc === 'number' ? p.purchaseCountCalc : 0;
			if (!isNaN(price)) {
				sumSales += price * cnt;
			}
			sumPurchase += cnt;
		});

		const avgPurchase = Math.round(sumPurchase / finalProducts.length);

		result.sumPurchaseCount = sumPurchase;
		result.sumSales = sumSales;

		// 필요시 개별 상품 단에서도 확인 가능:
		// p.purchaseCount (원본), p.purchaseCountCalc (실제/추정 혼합 계산용)
	})();
	//여기까지
	
	result.productList = productList;
//	console.log(productList)
	//relatedKeywords
	  
	result.relatedKeywords = pageProps.relatedQueries.map(item => item.query);

	result.priceCount = priceCount;
	
	const categoryList = [];
	let categoryTotalCount = 0;

	for (let i = 0; i < productList.length; i++) {
		const item = productList[i];
		

		if (!item.hasOwnProperty("adId")) {
			let tempCategoryString = "";
			const category1Name = item.category1Name || "";
			const category2Name = item.category2Name || "";
			const category3Name = item.category3Name || "";
			const category4Name = item.category4Name || "";

			tempCategoryString = `${category1Name} > ${category2Name} > ${category3Name} > ${category4Name}`;
			
			
			
			while (tempCategoryString.endsWith(" > ")) {
				tempCategoryString = tempCategoryString.slice(0, tempCategoryString.lastIndexOf(" > "));
			}

			let tempCategoryCode = "";
			const category1Id = item.category1Id || "";
			const category2Id = item.category2Id || "";
			const category3Id = item.category3Id || "";
			const category4Id = item.category4Id || "";

			tempCategoryCode = category4Id || category3Id || category2Id || category1Id;

			let isCategory = false;

			for (let j = 0; j < categoryList.length; j++) {
				const data = categoryList[j];
				if (data.categoryName === tempCategoryString) {
					data.categoryCount = String(Number(data.categoryCount) + 1);
					isCategory = true;
					break;
				}
			}

			if (!isCategory) {
				categoryList.push({
					categoryName: tempCategoryString,
					categoryCount: "1",
					categoryCode: tempCategoryCode
				});
			}

			categoryTotalCount++;
		}
	}

	// 퍼센트 포맷 (소수점 2자리 고정)
	for (let j = 0; j < categoryList.length; j++) {
		const data = categoryList[j];
		const cnt = Number(data.categoryCount);
		const categoryCountRate = (cnt / categoryTotalCount) * 100;
		data.categoryCountRate = categoryCountRate.toFixed(2); // 퍼센트 값
	}
	result.categoryList = categoryList;
	
	// 정렬 (카테고리 개수 내림차순)
	categoryList.sort((a, b) => Number(b.categoryCount) - Number(a.categoryCount));

	let categoryString = "";
	let categoryCode = "";

	if (categoryList.length > 0) {
		categoryString = categoryList[0].categoryName;
		categoryCode = categoryList[0].categoryCode;
		result.categoryCode = categoryCode;
	}
	
	
	
	
	return result;
}


function parseCoupangAutoKeyword(json) {
	const result = {};
	
	const keywordList = json.map(item => item.keyword);
	result.keywordList = keywordList;
	return result;
}
function parseShoppingResultM(json) {
	const result = {};
	const productList = new Array();

	const props = json.props;
	const pageProps = props.pageProps;
	const compositeProducts = pageProps.compositeProducts;
	const products = compositeProducts.list;
    
//    let partialSearched = false;        //일치검색 여부
//    if(pageProps.partialSearched)
//        partialSearched = pageProps.partialSearched;
//    result.partialSearched = partialSearched;

	let ranking = 1;
	let rankingIncludeAd = 1;
	let priceCount = 0;
	
	products.forEach(productItem => {
		let foundProduct = {};
		let product = productItem.item;

		let shopLink = '';
		if (product.mallProductUrl) {   
			shopLink = product.mallProductUrl;
		} else if (product.productUrl) {
			shopLink = product.productUrl;
		} else {
			shopLink = '';
		}
		foundProduct.link = shopLink;

		if(product.hasOwnProperty("adId"))
			foundProduct.adId = product.adId;
		
		foundProduct.scoreInfo = product.scoreInfo;
		foundProduct.openDate = product.openDate;
		
		
		foundProduct.category1Id = product.category1Id;
		foundProduct.category2Id = product.category2Id;
		foundProduct.category3Id = product.category3Id;
		foundProduct.category4Id = product.category4Id;
		
		foundProduct.category1Name = product.category1Name;
		foundProduct.category2Name = product.category2Name;
		foundProduct.category3Name = product.category3Name;
		foundProduct.category4Name = product.category4Name;
		
		let categoryString = "";

		if (product.category1Name)
			categoryString += ">" + product.category1Name;
		if (product.category2Name)
			categoryString += ">" + product.category2Name;
		if (product.category3Name)
			categoryString += ">" + product.category3Name;
		if (product.category4Name)
			categoryString += ">" + product.category4Name;

		if (categoryString.startsWith(">"))
			categoryString = categoryString.substring(1).trim();

		if (categoryString.endsWith(">"))
			categoryString = categoryString.substring(0, categoryString.lastIndexOf(">")).trim();
		
		foundProduct.categoryName = categoryString;
		foundProduct.price = product.price;
		
		if (product?.mallInfoCache?.mallGrade) {
			const mallGrade = String(product.mallInfoCache.mallGrade);

			const gradeMap = {
				"M44004": "파워",
				"M44003": "빅파워",
				"M44002": "프리미엄",
				"M44005": "굿서비스",
				"M44001": "플래티넘"
			};

			foundProduct.mallGrade = gradeMap[mallGrade] || "";
		}else{
			foundProduct.mallGrade = "";
		}

		
		let mallCount = 0;
		if(product.mallCount)
			mallCount = product.mallCount;
		foundProduct.mallCount = mallCount;

		if(mallCount > 0 && product.lowMallList){
			let shopList = product.lowMallList;
			let mallList = new Array();

			for (const shop of shopList) {
				if(shop.name){
					let mallName = shop.name.replace(" ", "");
					mallList.push(mallName);
				}else{
					mallList.push("UNKNOWN");
				}
			}
			foundProduct.mallList = mallList;
			foundProduct.isPriceProduct = true;
			priceCount++;
		}else{
			let mallName = '';
			if(product.mallName){
				mallName = product.mallName.replace(" ", "");
				foundProduct.mallName = mallName;
			}else{
				foundProduct.mallName = "UNKNOWN";
			}
			foundProduct.isPriceProduct = false;
		}

			
		let title = "";
		if(product.productTitle)
			title = product.productTitle;
		else
			title = product.productName;
		foundProduct.title = title;

		let nvMid = "";		
		if(product.id)
			nvMid = product.id;
		else
			nvMid = product.nvMid;
		foundProduct.nvMid = nvMid;
		
		let mallPid = "";
		if(product.mallProductId)
			mallPid = product.mallProductId;
		foundProduct.mallPid = mallPid;

		let img = "";
		if(product.imageUrl)
			img = product.imageUrl;
		else
			img = product.productImgUrl;
		foundProduct.img = img;

		let productDate = "";
		if(product.openDate)
			productDate = product.openDate;						
		if (productDate.length > 8) productDate = productDate.substring(0, 8);
		foundProduct.productDate = productDate;

		
		if(foundProduct.isPriceProduct)
			foundProduct.link = 'https://search.shopping.naver.com/catalog/' + nvMid;
		
		let reviewCount = -1;
		if(product.reviewCount)
			reviewCount = product.reviewCount;			
		foundProduct.reviewCount = reviewCount;

		let purchaseCount = -1;
		if(product.purchaseCnt)
			purchaseCount = product.purchaseCnt;
		foundProduct.purchaseCount = purchaseCount;

		let keepCount = -1;
		if(product.keepCnt)
			keepCount = product.keepCnt;						
		foundProduct.keepCount = keepCount;
		
		let rankingType = "";
		let searchResultType = "";
		let isHotDeal = product.isHotDeal;
		if(isHotDeal == 1){
			rankingType = "H";
			searchResultType = "핫";
		}else if(mallCount > 0){
			rankingType = "L";
			searchResultType = "가";
		}else{
			if (shopLink.indexOf("smartstore.naver.com") > -1){
				rankingType = "N";
				searchResultType = "스";
			}else if (shopLink.indexOf("shopping.naver.com/style") > -1
					|| shopLink.indexOf("shopping.naver.com/department") > -1
					|| shopLink.indexOf("shopping.naver.com/outlet") > -1
					|| shopLink.indexOf("shopping.naver.com/beauty") > -1
					|| shopLink.indexOf("shopping.naver.com/living") > -1
					|| shopLink.indexOf("shopping.naver.com/fresh") > -1
					|| shopLink.indexOf("shopping.naver.com/art") > -1)
			{
				rankingType = "W";
				searchResultType = "윈";
			}else{
				rankingType = "I";
				searchResultType = "자";
			}
		}
		foundProduct.rankingType = rankingType;
		foundProduct.searchResultType = searchResultType;
		
		foundProduct.ranking = ranking;
		foundProduct.rankingIncludeAd = rankingIncludeAd;

		if(product.adId){
			foundProduct.isAd = true;
		}else{
			foundProduct.isAd = false;
			ranking++;
		}
		rankingIncludeAd++;

		productList.push(foundProduct);
	});
	
	
	//여기부터
	(() => {
		const productListRaw = productList;
		if (!Array.isArray(productListRaw)) return;

		const filteredList = productListRaw.filter(p => p.isAd === false);

		const knownList = filteredList.filter(p => typeof p.purchaseCount === 'number' && p.purchaseCount >= 0);
		const unknownList = filteredList.filter(
			p => (typeof p.purchaseCount !== 'number' || p.purchaseCount < 0) && p.isPriceProduct !== true
		);

		const sortedKnown = [...knownList].sort((a, b) => a.rankingIncludeAd - b.rankingIncludeAd);
		const rankArr = sortedKnown.map(p => p.rankingIncludeAd);
		const countArr = sortedKnown.map(p => p.purchaseCount);

		const estimateCount = (rank) => {
			if (rankArr.length === 0) return 0;
			if (rank <= rankArr[0]) return countArr[0];
			if (rank >= rankArr[rankArr.length - 1]) return countArr[countArr.length - 1];
			for (let i = 0; i < rankArr.length - 1; i++) {
				const r1 = rankArr[i], r2 = rankArr[i + 1];
				const c1 = countArr[i], c2 = countArr[i + 1];
				if (rank >= r1 && rank <= r2) {
					const ratio = (rank - r1) / (r2 - r1);
					return Math.round(c1 + (c2 - c1) * ratio);
				}
			}
			return 0;
		};

		unknownList.forEach(p => {
			p.purchaseCount = estimateCount(p.rankingIncludeAd);
		});

		const finalProducts = [...knownList, ...unknownList];

		let sumSales = 0;
		let sumPurchase = 0;

		finalProducts.forEach(p => {
			const price = parseInt(p.price, 10);
			if (!isNaN(price)) {
				sumSales += price * p.purchaseCount;
			}
			sumPurchase += p.purchaseCount;
		});

		const avgPurchase = Math.round(sumPurchase / finalProducts.length);

		result.sumPurchaseCount = sumPurchase;
		result.sumSales = sumSales;
		
//		console.log('총 판매건수:', sumPurchase);
//		console.log('총 매출:', sumSales.toLocaleString(), '원');
//		console.log('평균 판매건수:', avgPurchase);
	})();
	//여기까지
	
	result.productList = productList;
//	console.log(productList)
	//relatedKeywords
//	result.relatedKeywords = pageProps.relatedTags;
	result.relatedKeywords = pageProps.relatedQueries.map(item => item.query);
	
	
	
	result.priceCount = priceCount;
	
	const categoryList = [];
	let categoryTotalCount = 0;

	for (let i = 0; i < productList.length; i++) {
		const item = productList[i];
		

		if (!item.hasOwnProperty("adId")) {
			let tempCategoryString = "";
			const category1Name = item.category1Name || "";
			const category2Name = item.category2Name || "";
			const category3Name = item.category3Name || "";
			const category4Name = item.category4Name || "";

			tempCategoryString = `${category1Name} > ${category2Name} > ${category3Name} > ${category4Name}`;
			
			
			
			while (tempCategoryString.endsWith(" > ")) {
				tempCategoryString = tempCategoryString.slice(0, tempCategoryString.lastIndexOf(" > "));
			}

			let tempCategoryCode = "";
			const category1Id = item.category1Id || "";
			const category2Id = item.category2Id || "";
			const category3Id = item.category3Id || "";
			const category4Id = item.category4Id || "";

			tempCategoryCode = category4Id || category3Id || category2Id || category1Id;

			let isCategory = false;

			for (let j = 0; j < categoryList.length; j++) {
				const data = categoryList[j];
				if (data.categoryName === tempCategoryString) {
					data.categoryCount = String(Number(data.categoryCount) + 1);
					isCategory = true;
					break;
				}
			}

			if (!isCategory) {
				categoryList.push({
					categoryName: tempCategoryString,
					categoryCount: "1",
					categoryCode: tempCategoryCode
				});
			}

			categoryTotalCount++;
		}
	}

	// 퍼센트 포맷 (소수점 2자리 고정)
	for (let j = 0; j < categoryList.length; j++) {
		const data = categoryList[j];
		const cnt = Number(data.categoryCount);
		const categoryCountRate = (cnt / categoryTotalCount) * 100;
		data.categoryCountRate = categoryCountRate.toFixed(2); // 퍼센트 값
	}
	result.categoryList = categoryList;
	
	// 정렬 (카테고리 개수 내림차순)
	categoryList.sort((a, b) => Number(b.categoryCount) - Number(a.categoryCount));

	let categoryString = "";
	let categoryCode = "";

	if (categoryList.length > 0) {
		categoryString = categoryList[0].categoryName;
		categoryCode = categoryList[0].categoryCode;
		result.categoryCode = categoryCode;
	}
	
	
	
	
	return result;
}

function removeEmojis(str) {
	return str.replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu, '');
}

function cutByByte(str, maxBytes = 1000) {
	let bytes = 0;
	let result = '';

	for (let i = 0; i < str.length; i++) {
		const char = str[i];
		const code = char.codePointAt(0);

		let byteSize = 0;
		if (code <= 0x007f) {
			byteSize = 1; // ASCII
		} else if (code <= 0x07ff) {
			byteSize = 2;
		} else if (code <= 0xffff) {
			byteSize = 3;
		} else {
			byteSize = 4; // emoji 등
			i++; // surrogate pair 차지
		}

		if (bytes + byteSize > maxBytes) break;

		result += char;
		bytes += byteSize;
	}

	return result;
}


function parseShoppingAPIResult(obj) {
	const result = {};

	const shoppingResult = obj.shoppingResult;

	result.strQueryType = shoppingResult.strQueryType || "";
	result.query = shoppingResult.query || "";
	result.stopwordQuery = shoppingResult.stopwordQuery || "";
	result.totalCount = shoppingResult.total || 0;
	result.termCount = shoppingResult.termCount || 0;
	// nluTerms
	result.nluTerms = (shoppingResult.nluTerms || []).map(term => ({
		nluKeyword: term.keyword,
		nluType: term.type
	}));

	// terms
	result.termsList = shoppingResult.terms || [];


	
	// categories
	const cmpOrg = shoppingResult.cmpOrg || {};
	["category1", "category2", "category3", "category4"].forEach(catKey => {
		const categories = (cmpOrg[catKey]?.categories || []).map(cat => ({
			id: cat.id,
			name: cat.name,
			score: cat.relevance
		})).filter(cat => cat.name !== "");
		result[`categories${catKey.slice(-1)}`] = categories;
		result[`isCategory${catKey.slice(-1)}`] = categories.length > 0;
	});

	// productList
	const products = shoppingResult.products || [];
	const productCategoryList = [];
	const productList = [];
	let categoryTotalCount = 0;
	
	for (let i = 0; i < products.length; i++) {
		const p = products[i];
		
		const attributeValueList = [];
		if (p.attributeValue && typeof p.attributeValue === "string") {
			p.attributeValue.split('|').forEach(attr => {
				const trimmed = attr.trim();
				if (trimmed) attributeValueList.push(trimmed);
			});
		}
		
		const characterValueList = [];
		if (p.characterValue && typeof p.characterValue === "string") {
			p.characterValue.split('|').forEach(char => {
				const trimmed = char.trim();
				if (trimmed) characterValueList.push(trimmed);
			});
		}
		
		const tagList = [];
		if (p.manuTag && typeof p.manuTag === "string") {
			p.manuTag.split(',').forEach(tag => {
				const trimmed = tag.trim();
				if (trimmed) tagList.push(trimmed);
			});
		}
		
		
		const productData = {
			rank: p.rank ?? 0,
			id: p.id ?? "",
			openDate: p.openDate ?? "",
			score: p.scoreInfo ?? -1,
			category1Name: p.category1Name ?? "",
			category2Name: p.category2Name ?? "",
			category3Name: p.category3Name ?? "",
			category4Name: p.category4Name ?? "",
			category1Id: p.category1Id ?? "",
			category2Id: p.category2Id ?? "",
			category3Id: p.category3Id ?? "",
			category4Id: p.category4Id ?? "",
			mallCount: p.mallCount ?? 0,
			productTitle: p.productTitle ?? "",
			reviewCount: p.reviewCount ?? -1,
			price: p.lowPrice ?? -1,
			deliveryPrice: p.dlvryLowPrice ?? -1,
			imageUrl: p.imageUrl ?? "",
			mallProductId: p.mallProductId ?? "",
			mallName: p.mallName ?? "",
			keepCnt: p.keepCnt ?? -1,
			purchaseCnt: p.purchaseCnt ?? -1,
			lowMallList: (p.lowMallList || []).map(mall => ({
				nvMid: mall.nvMid,
				name: mall.name
			})),
			attributeValueList:attributeValueList,
			characterValueList:characterValueList,
			tagList:tagList,
			imageCount:p.additionalImageCount,
			mallUrl:p.mallPcUrl,
			CR:p.crUrl
		};

		// 카탈로그 여부 판단
		if (productData.lowMallList.length > 0) {
			productData.mallProductUrl = `https://search.shopping.naver.com/catalog/${p.id}`;
			productData.isCatalog = true;
		} else {
			productData.mallProductUrl = p.mallProductUrl ?? "";
			productData.isCatalog = false;
		}
		
		// 메인 카테고리
		if (i === 0) {
			result.mainCategoryName = p.category1Name ?? "";
			result.mainCategoryId = p.category1Id ?? "";
		}

		// 카테고리 이름 조합
		const categoryName = [
			p.category1Name, p.category2Name, p.category3Name, p.category4Name
		].filter(Boolean).join(">");

		// 카테고리 개수 집계
		let existing = productCategoryList.find(c => c.categoryName === categoryName);
		if (existing) {
			existing.categoryCount = String(+existing.categoryCount + 1);
		} else {
			productCategoryList.push({ categoryName, categoryCount: "1" });
		}
		categoryTotalCount++;

		productList.push(productData);
	}

	// category 비율 계산
	productCategoryList.forEach(c => {
		const rate = (parseInt(c.categoryCount) / categoryTotalCount) * 100;
		c.categoryCountRate = rate.toFixed(1); // 소수점 1자리
	});

	// 정렬
	productCategoryList.sort((a, b) => +b.categoryCount - +a.categoryCount);

	result.productCategoryList = productCategoryList;
	result.productList = productList;
	
	return result;
}


function parseShoppingProductResult(obj) {
	const result = {};
	//
//	console.log(JSON.stringify(obj));
	
	const simpleProductForDetailPage = obj.simpleProductForDetailPage;
	const A = simpleProductForDetailPage.A;
	
	const smartStoreV2 = obj?.smartStoreV2;
	const channel = smartStoreV2?.channel || obj?.channel?.A || obj?.channel;

	
	const epInfo = A.epInfo;
	if (epInfo?.syncNvMid !== undefined) {
		const syncNvMid = epInfo.syncNvMid;
		const productId = A.id;
		const productNo = A.productNo;
		const imageUrl = A.representativeImageUrl;
		const name = A.name;
		
		result.productId = productId;
		result.productNo = productNo;
		result.price = A.salePrice;
		result.name = name;
		result.imageUrl = imageUrl;
		result.syncNvMid = syncNvMid;
		result.mallSeq = channel?.mallSeq;
		result.merchantNo = channel?.payReferenceKey;
		result.channelId = channel?.id;
		result.accountNo = channel?.accountNo;
		result.naSiteId = channel?.naSiteId;
		result.channelUid = channel?.channelUid;
		result.storeId = channel?.url;
		result.shopName = channel?.channelName;
		result.tags = A.seoInfo?.sellerTags?.map(tag => tag.text);
		result.reviewScore = A.reviewAmount?.averageReviewScore;
		result.category = A.category?.wholeCategoryName;
		result.isProduct = true;
		result.storeType = channel?.storeExhibitionType;
	}else{
		result.isProduct = false;
	}
	
	
	return result;
}

function delay(ms) {
	return new Promise(resolve => setTimeout(resolve, ms));
}
function parseCoupangProductUrl(url) {
	const result = {};

	// 1. productId: /vp/products/ 다음에 나오는 숫자
	const productMatch = url.match(/\/vp\/products\/(\d+)/);
	if (productMatch) {
		result.productId = productMatch[1];
	}

	// 2. itemId와 vendorItemId: 쿼리스트링에서 추출
	const urlObj = new URL(url);
	result.itemId = urlObj.searchParams.get("itemId");
	result.vendorItemId = urlObj.searchParams.get("vendorItemId");

	return result;
}

function sendReceiveProcess(sendMessage, receiveMessage, parameter, errorCallback){
	return new Promise((resolve, reject) => {
		if(receiveMessage != ''){
			function handleMessage(event) {
				if (event.source !== window) return;
				if (event.data?.source !== receiveMessage) return;
	
				window.removeEventListener("message", handleMessage);
				
				const status = event.data.status;
//				console.log(event.data)
				if(status == 200){
					resolve(event.data.payload);
				}else{
					
					//
					if(errorCallback == null){
						
					}else{
						errorCallback();
					}
	
					if(status == 9998 || status == 490){
						try{
							if(event.data?.tabId > 0){
								
								popupProtectNew(protect, '잦은 검색으로 네이버 차단이 발생할수 있습니다.<br>네이버 로그인 및 검색 캡챠 해제를 완료해주세요', function(){
									sendReceiveProcess('focusTab', '', {tabId: event.data?.tabId});
								}, '캡챠 풀러 가기');
//								console.log(event.data?.tabId)
							}else{
								const connectUrl = parameter.url ? parameter.url : (event.data.source == 'getNSearchResultResultM' ? 'https://msearch.shopping.naver.com/search/all?query=팝마트' : 'https://search.shopping.naver.com/search/all?query=팝마트');
								popupProtect(protect, '잦은 검색으로 네이버 차단이 발생할수 있습니다.<br>네이버 로그인 및 검색 캡챠 해제를 완료해주세요', connectUrl, '캡챠 풀러 가기');
							}
							
							
						}catch(e){
							alert('네이버 검색 요망(캡챠 발생)');
						}finally{
							$('.overlay').hide();
						}
					}else if(status == 9997 || status == 429){
						
						try{
							popupProtect(protect, '네이버 연동이 필요합니다.<br>네이버 로그인을 완료 후 쇼핑검색 1회 진행해주세요', 'https://search.shopping.naver.com/all', '네이버 바로가기');
						}catch(e){
							alert('검색제한 : 네이버 로그인 필요');
						}finally{
							$('.overlay').hide();
						}
					}else if(status == 204){
						$('.overlay').hide();
						
					}else{
						if(event.data?.tabId > 0){
							sendReceiveProcess('focusTab', '', {tabId: event.data?.tabId});
//							console.log(event.data?.tabId)
						}
						reject(new Error(status + ' 오류 발생 : ' + sendMessage));
					}
					
	//				throw new Error(event.data.status + '오류 발생 : ' + sendMessage)
					
				}
			}
	
			window.addEventListener("message", handleMessage);
		}
		// 요청 보내기
		window.postMessage({
			source: sendMessage,
			payload: parameter
		}, "*");
	});
}

function sendReceiveProcessNoAlert(sendMessage, receiveMessage, parameter, errorCallback){
	
	return new Promise((resolve, reject) => {
		if(receiveMessage != ''){
			function handleMessage(event) {
				if (event.source !== window) return;
				if (event.data?.source !== receiveMessage) return;
	
				window.removeEventListener("message", handleMessage);
				
				const status = event.data.status;
				 
				if(status == 200){
					resolve(event.data.payload);
				}else{
				
					console.log("Error : " + (event.data?.error) || "알 수 없는 오류");
					
					if(errorCallback == null){
						
					}else{
						errorCallback();
					}
	//				throw new Error(event.data.status + '오류 발생 : ' + sendMessage)
					reject(new Error(status + ' 오류 발생 : ' + sendMessage));
	
				}
					
				
				
			}
	
			window.addEventListener("message", handleMessage);
		}
		// 요청 보내기
		window.postMessage({
			source: sendMessage,
			payload: parameter
		}, "*");
	});
}

function getTimestamp(){

	const now = new Date();
	const timestamp = now.getFullYear().toString()
		+ String(now.getMonth() + 1).padStart(2, '0')
		+ String(now.getDate()).padStart(2, '0')
		+ String(now.getHours()).padStart(2, '0')
		+ String(now.getMinutes()).padStart(2, '0')
		+ String(now.getSeconds()).padStart(2, '0');
	return timestamp;
}
function toPercent(value) {
	return (value * 100).toFixed(2) + '%';
}
function toFidex(value, num) {
	return value.toFixed(2);
}

function cleanKeyword(input) {
	// 1. 이모지 제거 (기본 유니코드 범위 기반)
	input = input.replace(/[\u{1F300}-\u{1FAFF}]/gu, "");

	// 2. 한글, 영문, 숫자, -, ., +, 공백 허용
	input = input.replace(/[^가-힣a-zA-Z0-9\-.\+\s&_!]/g, "");



	
	
	// 3. 대문자로 변환
	return input.toUpperCase();
}

function cleanKeyword2(input) {
	// 1. 이모지 제거 (기본 유니코드 범위 기반)
	input = input.replace(/[\u{1F300}-\u{1FAFF}]/gu, "");

	// 2. 한글자음, 한글, 영문, 숫자, -, ., +, 공백 허용
	input = input.replace(/[^가-힣\u3130-\u318Fa-zA-Z0-9\-.\+\s&_!]/g, "");


	
	

	return input;
}

function parseShoppingProductDeliveryResult(obj) {
	const result = {};
	
	const productDeliveryLeadTimes = obj?.productDeliveryLeadTimes;
	
	if (productDeliveryLeadTimes) {
		
		const toalCount7Days = productDeliveryLeadTimes.reduce((sum, item) => sum + item.leadTimeCount, 0);
		result.toalCount7Days = toalCount7Days; 
		
		result.isDeliveryInfo = true;
	}else{
		result.isDeliveryInfo = false;
	}
	
	
	return result;
}

function getExtensionVersion() {
	return new Promise((resolve) => {
		isHelpstoreExtensionInstalled().then(async (installed) => {
			if (installed) {
				const result = await sendReceiveProcess(
					"getHelpstoreExtensionVersion",
					"getHelpstoreExtensionVersionResult",
					{}
				);
				resolve(result); // ✅ 버전 리턴
			} else {
				resolve(null); // ❌ 확장 미설치
			}
		});
	});
}

function isCoupangLogin(){
	return new Promise((resolve) => {
		// 응답 리스너 1회용으로 등록
		function handleMessage(event) {			if (event.source !== window) return;
			if (event.data?.source !== "isLoginCoupangResult") return;

			window.removeEventListener("message", handleMessage);
			
			if(event.data.payload.success)
				resolve(true);
			else
				resolve(false);
		}
		
		window.addEventListener("message", handleMessage);
		
		// 요청 보내기
		window.postMessage({
			source: "isLoginCoupang",
		}, "*");
	});
}

function isWingLogin(){
	return new Promise((resolve) => {
		// 응답 리스너 1회용으로 등록
		function handleMessage(event) {		
			if (event.source !== window) return;
			if (event.data?.source !== "wingLoginCheckResult") return;

			window.removeEventListener("message", handleMessage);
			
			if(event.data.payload.success)
				resolve(true);
			else
				resolve(false);
		}
		
		window.addEventListener("message", handleMessage);
		
		// 요청 보내기
		window.postMessage({
			source: "isLoginWing",
		}, "*");
	});
}

function parseCoupangWingProductResult(json) {
	const result = {};
	const productList = new Array();
	
	const products = json.result;

	var ranking = 1;
	
	products.forEach(product => {
		if(ranking <= 40){
			
			let foundProduct = {};
			
			foundProduct.productId = product.productId;
			foundProduct.productName = product.productName;
			foundProduct.brandName = product.brandName;
			foundProduct.manufacture = product.manufacture;
			foundProduct.itemId = product.itemId;
			foundProduct.itemName = product.itemName;
			
			foundProduct.itemCountOfProduct = product.itemCountOfProduct;
			foundProduct.imagePath = 'https://thumbnail8.coupangcdn.com/thumbnails/remote/320x320ex/image/' + product.imagePath;
			foundProduct.salePrice = product.salePrice;
			
			foundProduct.vendorItemId = product.vendorItemId;
			foundProduct.ratingCount = product.ratingCount;
			foundProduct.rating = product.rating;
			foundProduct.pvLast28Day = product.pvLast28Day;
			foundProduct.salesLast28d = product.salesLast28d;
			foundProduct.salesLast28dAmount = product.salesLast28d * product.salePrice;
			foundProduct.cvr = (product.salesLast28d / product.pvLast28Day) * 100;
			
	//		foundProduct.matchType = product.matchType;
	//		foundProduct.deliveryMethod = product.deliveryMethod;
			
			foundProduct.link = 'https://www.coupang.com/vp/products/'+product.productId+'?itemId='+product.itemId+'&vendorItemId=' + product.vendorItemId;
			foundProduct.categories = product.displayCategoryInfo;
			if (Array.isArray(product.displayCategoryInfo) && product.displayCategoryInfo.length > 0) {
				// leaf 카테고리 → 배열 마지막 categoryHierarchy 사용
				 
				foundProduct.category = product.displayCategoryInfo[product.displayCategoryInfo.length - 1].categoryHierarchy;
				foundProduct.categoryCode = product.displayCategoryInfo[product.displayCategoryInfo.length - 1].leafCategoryCode;
			} else {
				foundProduct.category = ''; // 카테고리 없는 경우
				foundProduct.categoryCode = '';
			}
			foundProduct.ranking = ranking;
			ranking++;
			productList.push(foundProduct);
		}
	});
	
	let totalSalesLast28d = productList.reduce((sum, item) => sum + item.salesLast28d, 0);
	let totalSalesLast28dAmount = productList.reduce((sum, item) => sum + item.salesLast28dAmount, 0);

		
	result.sumPurchaseCount = totalSalesLast28d;
	result.sumSales = totalSalesLast28dAmount;
	result.productCount = productList.length;
	result.productList = productList;
	
//	result.mainCategoryCode = productList[0].categoryCode;
//	result.mainCategory = productList[0].category;
	
	let categoryDistribution = {};
	let categoryCodeDistribution = {};
	let totalCount = productList.length;
	
	productList.forEach(product => {
		if (Array.isArray(product.categories)) {
			product.categories.forEach(cat => {
				let categoryName = cat.categoryHierarchy; // categoryName으로 사용
				let categoryCode = cat.leafCategoryCode; // categoryName으로 사용

				if (!categoryDistribution[categoryName]) {
					categoryDistribution[categoryName] = 0;
				}
				
				if (!categoryCodeDistribution[categoryCode]) {
					categoryCodeDistribution[categoryCode] = 0;
				}
				
				categoryDistribution[categoryName]++;
				categoryCodeDistribution[categoryCode]++;
				
			});
		}
	});

	// 비율(%)로 변환 + array로 변환
	let categoryRateArray = Object.entries(categoryDistribution).map(([categoryName, count]) => {
		return {
			categoryName: categoryName,
			rate: ((count / totalCount) * 100).toFixed(2) // 소수점 2자리 %
		};
	});

	// 비율(%)로 변환 + array로 변환
	let categoryCodeRateArray = Object.entries(categoryCodeDistribution).map(([categoryCode, count]) => {
		return {
			categoryCode: categoryCode,
			rate: ((count / totalCount) * 100).toFixed(2) // 소수점 2자리 %
		};
	});
	
	// 정렬 (비율 높은 순)
	categoryRateArray.sort((a, b) => b.rate - a.rate);
	categoryCodeRateArray.sort((a, b) => b.rate - a.rate);
	
	result.categoryList = categoryRateArray;
	
	if(categoryCodeRateArray.length > 0){
		result.mainCategoryCode = categoryCodeRateArray[0].categoryCode;
		result.mainCategory = categoryRateArray[0].categoryName;
	}else{
		result.mainCategoryCode = '';
		result.mainCategory = '';
	}
	
	
	return result;
}

function cmpSemver(a, b){
	// 1.0.1, 1.0.1-beta.2 같은 것도 숫자만 비교
	const pa = (a || '').split(/[.-]/).map(s => /^\d+$/.test(s) ? +s : NaN).filter(n => !Number.isNaN(n));
	const pb = (b || '').split(/[.-]/).map(s => /^\d+$/.test(s) ? +s : NaN).filter(n => !Number.isNaN(n));
	const len = Math.max(pa.length, pb.length);
	for (let i = 0; i < len; i++) {
		const x = pa[i] ?? 0, y = pb[i] ?? 0;
		if (x > y) return 1;
		if (x < y) return -1;
	}
	return 0; // 동일
}

const gteSemver = (a, b) => cmpSemver(a, b) >= 0;

function pickJsonLdStringsJQ(responseString) {
  const $root = $('<div>').append($.parseHTML(responseString));

  const productJsonString = ($root.find('script[type="application/ld+json"][src="product"]').first().text() || '').trim() || null;
  const breadcrumbJsonString = ($root.find('script[type="application/ld+json"][src="breadcrumb"]').first().text() || '').trim() || null;

  return { productJsonString, breadcrumbJsonString };
}

function breadcrumbPath(breadcrumbJsonString) {
	const data = JSON.parse(breadcrumbJsonString);
	const list = data.itemListElement;
	
	// 중첩 배열 풀기
	const flat = (arr) => arr.flatMap(x => Array.isArray(x) ? flat(x) : [x]);
	
	const items = flat(list)
		.filter(x => x && x['@type'] === 'ListItem' && x.position !== 1)
		.sort((a, b) => a.position - b.position);
	return items.map(x => x.name).join('>');
}

async function closeTab(url){
	await sendReceiveProcess('closeTabByH', '', {url:url});
}


//'6.17.화' / '3.16.일' 같은 문자열을 yyyy-mm-dd 로 변환 (연도는 인자로 받음)
function formatKoreanMDToYMD(mdStr, fallbackYear) {
  if (!mdStr || typeof mdStr !== 'string') return null;
  const s = mdStr.trim();

  // 1) YYYY.M.D.(요일) 또는 YY.M.D.(요일)
  let m = s.match(/^(\d{2,4})\.(\d{1,2})\.(\d{1,2})(?:\.[^0-9]*)?$/);
  if (m) {
    let y = parseInt(m[1], 10);
    const month = parseInt(m[2], 10);
    const day = parseInt(m[3], 10);
    if (m[1].length === 2) y = 2000 + y; // 24 -> 2024
    if (month < 1 || month > 12 || day < 1 || day > 31) return null;
    return `${y}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }

  // 2) M.D.(요일) → 연도는 fallbackYear 사용
  m = s.match(/^(\d{1,2})\.(\d{1,2})(?:\.[^0-9]*)?$/);
  if (m) {
    const y = parseInt(fallbackYear, 10);
    const month = parseInt(m[1], 10);
    const day = parseInt(m[2], 10);
    if (!Number.isFinite(y) || month < 1 || month > 12 || day < 1 || day > 31) return null;
    return `${y}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }

  return null;
}

// ISO → 로컬 yyyy-mm-dd HH:mi:ss
function formatISOToLocal(iso) {
	try {
		const d = new Date(iso);
		const yyyy = d.getFullYear();
		const mm = String(d.getMonth() + 1).padStart(2, '0');
		const dd = String(d.getDate()).padStart(2, '0');
		const HH = String(d.getHours()).padStart(2, '0');
		const mi = String(d.getMinutes()).padStart(2, '0');
		const ss = String(d.getSeconds()).padStart(2, '0');
		return `${yyyy}-${mm}-${dd} ${HH}:${mi}:${ss}`;
	} catch {
		return null;
	}
}

function numOrNull(v) {
	const n = Number(v);
	return Number.isFinite(n) ? n : null;
}



// 사용 예
// const result = extractReviews(YOUR_RESPONSE_OBJECT);
// console.log(result);

function sleep(ms) {
	return new Promise(resolve => setTimeout(resolve, ms));
}
function parseNaverPlaceReview(resp, pageSize) {
	// body -> [ { data: { visitorReviews: { items: [...] } } } ]
	const arr = resp?.body ?? [];
	const vr = arr[0]?.data?.visitorReviews;
	const items = Array.isArray(vr?.items) ? vr.items : [];

	const outItems = items.map(it => {
		const authorNickname = it?.author?.nickname ?? null;

		// created: '6.17.화' 같은 형식 → yyyy-mm-dd (연도는 대표방문일의 연도 우선, 없으면 현재 연도)
		const repISO = it?.representativeVisitDateTime || null; // '2025-06-01T01:00:00.000Z' 등
		const repDate = repISO ? new Date(repISO) : null;
		const baseYear = repDate ? repDate.getUTCFullYear() : (new Date()).getFullYear();
		const createdStr = formatKoreanMDToYMD(it?.created ?? null, baseYear);

		// visited: 대표 방문 시간이 있으면 yyyy-mm-dd HH:mi:ss, 없으면 'visited' 텍스트를 yyyy-mm-dd 로 파싱 시도
		let visitedOut = null;
		if (repISO) {
			visitedOut = formatISOToLocal(repISO); // yyyy-mm-dd HH:mi:ss (로컬 타임존 기준)
		} else if (it?.showRepresentativeVisitDateTime) {
			// 필드가 boolean일 가능성 → 별도 ISO가 없으면 의미 없음
			visitedOut = null;
		} else {
			visitedOut = formatKoreanMDToYMD(it?.visited ?? null, baseYear);
		}

		return {
			nickname: authorNickname,
			body: it?.body ?? null,
			bookingItemName: it?.bookingItemName ?? null, // (오타 주의: bookingItemName)
			created: createdStr,                           // yyyy-mm-dd
			reviewId: it?.reviewId ?? null,
			visited: visitedOut,                           // yyyy-mm-dd HH:mi:ss 또는 yyyy-mm-dd 또는 null
			thumbnail: it?.thumbnail ?? null,              // (오타 주의: thumbnail)
			cursor: it?.cursor ?? null,
			originType: it?.originType ?? null,
			receiptInfoUrl: it?.receiptInfoUrl ?? null,
			viewCount: numOrNull(it?.viewCount),
			visitCount: numOrNull(it?.visitCount)
		};
	});

	const lastCursor = outItems.length ? (outItems[outItems.length - 1].cursor ?? null) : null;

	const more = outItems.length === pageSize; // 딱 10개면 더 있음으로 간주
	const total = vr?.total;
	return { items: outItems, lastCursor, more , total:total};
}


/**
 * 네이버 플레이스 HTML에서 요약 정보와 Apollo State를 파싱한다.
 * @param {string} html - json.html 에서 읽어온 전체 HTML 문자열
 * @param {string|number} placeId - 숫자 placeId (예: 1559564560)
 * @returns {{
 *   meta: {
 *     reviewCount: number|null,
 *     blogReviewCount: number|null,
 *     thumbnail: string|null
 *   },
 *   place: {
 *     name: string|null,
 *     category: string|null,
 *     address: string|null,
 *     roadAddress: string|null,
 *     x: number|null,
 *     y: number|null,
 *     virtualPhone: string|null,
 *     talktalkUrl: string|null
 *   }
 * } | null}
 */
function parseNaverPlaceHtml(html, placeId) {
	try {
		if (!html || typeof html !== 'string') {
			console.error('parseNaverPlaceHtml: invalid html');
			return null;
		}
		const pid = String(placeId || '').trim();
		if (!/^\d+$/.test(pid)) {
			console.error('parseNaverPlaceHtml: invalid placeId');
			return null;
		}

		// HTML decode 유틸
		const decodeHtml = (s) => {
			if (s == null) return null;
			if (typeof DOMParser !== 'undefined') {
				const doc = new DOMParser().parseFromString(`<!doctype html><p>${s}</p>`, 'text/html');
				return doc.body.textContent || s;
			}
			return s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
		};

		// ==== 1) 메타 태그 파싱 (og:description, og:image) ====
		let ogDesc = null;
		let ogImage = null;

		if (typeof DOMParser !== 'undefined') {
			const doc = new DOMParser().parseFromString(html, 'text/html');
			const descEl = doc.querySelector('meta[property="og:description"], meta#og\\:description');
			const imgEl  = doc.querySelector('meta[property="og:image"], meta#og\\:image');
			ogDesc = descEl?.getAttribute('content') || null;
			ogImage = imgEl?.getAttribute('content') || null;
		} else {
			const mDesc = html.match(/<meta[^>]+property=["']og:description["'][^>]*content=["']([^"']+)["'][^>]*>/i);
			ogDesc = mDesc ? decodeHtml(mDesc[1]) : null;
			const mImg = html.match(/<meta[^>]+property=["']og:image["'][^>]*content=["']([^"']+)["'][^>]*>/i);
			ogImage = mImg ? decodeHtml(mImg[1]) : null;
		}

		let reviewCount = null, blogReviewCount = null;
		if (ogDesc) {
			const m = ogDesc.match(/방문자리뷰\s*([\d,]+).*블로그리뷰\s*([\d,]+)/);
			if (m) {
				reviewCount = Number(String(m[1]).replace(/,/g, '')) || 0;
				blogReviewCount = Number(String(m[2]).replace(/,/g, '')) || 0;
			}
		}
		const thumbnail = ogImage ? decodeHtml(ogImage) : null;

		// ==== 2) window.__APOLLO_STATE__ JSON 추출 ====
		const apolloMatch = html.match(/window\.__APOLLO_STATE__\s*=\s*(\{[\s\S]*?\});/);
		if (!apolloMatch) {
			console.error('parseNaverPlaceHtml: __APOLLO_STATE__ not found');
			return {
				meta: { reviewCount, blogReviewCount, thumbnail },
				place: {
					name: null, category: null, address: null, roadAddress: null,
					x: null, y: null, virtualPhone: null, talktalkUrl: null
				},
				keywords: null
			};
		}

		let apollo;
		try {
			apollo = JSON.parse(apolloMatch[1]);
		} catch (e) {
			console.error('parseNaverPlaceHtml: __APOLLO_STATE__ JSON parse failed', e);
			return null;
		}

		// ==== 유틸: __ref 해제 / 키 검색 ====
		const deref = (ref) => {
			if (!ref || typeof ref !== 'string') return null;
			return apollo[ref] || null;
		};
		const findInfoTabKeywordList = (obj) => {
			if (!obj || typeof obj !== 'object') return null;
			for (const k of Object.keys(obj)) {
				// informationTab(...) 형태 키에서 keywordList 찾아 반환
				if (/^informationTab\(/.test(k)) {
					const tab = obj[k];
					if (tab && typeof tab === 'object' && Array.isArray(tab.keywordList)) {
						return tab.keywordList.slice(); // shallow copy
					}
				}
			}
			return null;
		};

		// ==== 3) PlaceDetailBase:{placeId} 기본 필드 ====
		const key = `PlaceDetailBase:${pid}`;
		let base = apollo && apollo[key];
		if (!base || typeof base !== 'object') {
			const altKey = Object.keys(apollo || {}).find(k => /^PlaceDetailBase:\d+$/.test(k) && k.endsWith(`:${pid}`));
			base = altKey ? apollo[altKey] : null;
		}

		// ==== 4) ROOT_QUERY 경로로 keywordList 우선 수집 ====
		let keywords = null;
		const root = apollo && apollo.ROOT_QUERY;
		if (root && typeof root === 'object') {
			// 4-1) ROOT_QUERY 안의 placeDetail(...)에서 직접 정보탭 검색
			const placeDetailKey = Object.keys(root).find(k => /^placeDetail\(/.test(k));
			if (placeDetailKey) {
				const pd = root[placeDetailKey];
				if (pd && typeof pd === 'object') {
					// (A) placeDetail 객체 안쪽에서 informationTab(...).keywordList 찾기
					keywords = findInfoTabKeywordList(pd);

					// (B) 못 찾으면 base.__ref 따라가 PlaceDetailBase에서 검색
					if (!keywords && pd.base?.__ref) {
						const baseFromPd = deref(pd.base.__ref);
						if (baseFromPd) {
							keywords = findInfoTabKeywordList(baseFromPd);
						}
					}
				}
			}
		}

		// 4-2) 아직 없으면 Base 객체에서 시도
		if (!keywords && base) {
			keywords = findInfoTabKeywordList(base);
		}

		// 4-3) 그래도 없으면 전체 스캔(안전장치)
		if (!keywords) {
			for (const objKey of Object.keys(apollo)) {
				const obj = apollo[objKey];
				if (obj && typeof obj === 'object') {
					const ks = findInfoTabKeywordList(obj);
					if (ks) { keywords = ks; break; }
				}
			}
		}

		// ==== 5) 장소 기본 필드 ====
		const place = {
			name: base?.name ?? null,
			category: base?.category ?? null,
			address: base?.address ?? null,
			roadAddress: base?.roadAddress ?? null,
			x: toNum(base?.coordinate?.x),
			y: toNum(base?.coordinate?.y),
			virtualPhone: base?.virtualPhone ?? null,
			talktalkUrl: base?.talktalkUrl ?? null
		};

		return {
			meta: { reviewCount, blogReviewCount, thumbnail },
			place,
			keywords: Array.isArray(keywords) ? keywords : null
		};

	} catch (err) {
		console.error('parseNaverPlaceHtml: unexpected error', err);
		return null;
	}

	function toNum(v) {
		const n = Number(v);
		return Number.isFinite(n) ? n : null;
	}
}




function extractPlaceId(rawUrl) {
	  if (!rawUrl || typeof rawUrl !== "string") return null;

	  let url;
	  const trimmed = rawUrl.trim();
	  try {
	    url = new URL(trimmed);
	  } catch {
	    // 스킴이 빠진 경우 보정 (예: map.naver.com/...)
	    try { url = new URL("https://" + trimmed); }
	    catch { return null; }
	  }

	  const host = (url.hostname || "").toLowerCase();
	  const path = url.pathname || "";

	  // map.naver.com
	  if (host === "map.naver.com") {
	    // /p/(entry|smart-around)/place/{id}
	    let m = path.match(/^\/p\/(?:entry|smart-around)\/place\/(\d+)(?:\/|$)/);
	    if (m) return m[1];

	    // /p/search/{query}/place/{id}
	    m = path.match(/^\/p\/search\/[^/]+\/place\/(\d+)(?:\/|$)/);
	    if (m) return m[1];

	    return null;
	  }

	  // m.place.naver.com, pcmap.place.naver.com
	  if (host === "m.place.naver.com" || host === "pcmap.place.naver.com") {
	    // /place/{id}/... 또는 /{category}/{id}/...
	    const m = path.match(/^\/(?:place|[a-z]+)\/(\d+)(?:\/|$)/i);
	    return m ? m[1] : null;
	  }

	  return ''; // 지원 대상 아님
	}


function getKeywordTypeFromUrl(responseString){
	if (typeof responseString !== "string") {
		return { type: "Place", type2: "" };
	}

	if (responseString.includes("/nailshop/")) {
		return { type: "Beauty", type2: "nailshop" };
	} else if (responseString.includes("/hairshop/")) {
		return { type: "Beauty", type2: "hairshop" };
	} else if (responseString.includes("/hospital/")) {
		return { type: "Hospital", type2: "" };
	} else if (responseString.includes("/restaurant/")) {
		return { type: "Restaurant", type2: "" };
	} else if (responseString.includes("/accommodation/")) {
		return { type: "Accommodation", type2: "" };
	}else if (responseString.includes("/trip/")) {
		return { type: "Trip", type2: "" };
	}
	return { type: "Place", type2: "" };
	
}


function makeNumeric(sheet) {
	if (!sheet['!ref']) return;
	const range = XLSX.utils.decode_range(sheet['!ref']);

	for (let R = range.s.r + 1; R <= range.e.r; R++) { // 0번 row는 헤더라고 가정
		for (let C = range.s.c; C <= range.e.c; C++) {
			const addr = XLSX.utils.encode_cell({ r: R, c: C });
			const cell = sheet[addr];
			if (!cell || cell.t !== 's') continue;

			// 천단위 콤마 제거 후 숫자 여부 체크
			const raw = String(cell.v).replace(/,/g, '').trim();
			if (raw === '') continue;
			if (!isNaN(raw)) {
				cell.v = Number(raw);
				cell.t = 'n';
			}
		}
	}
}