(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['item'] = template({"1":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<tr>\r\n					<th scope=\"row\">\r\n						"
    + alias4(((helper = (helper = lookupProperty(helpers,"rank") || (depth0 != null ? lookupProperty(depth0,"rank") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank","hash":{},"data":data,"loc":{"start":{"line":92,"column":6},"end":{"line":92,"column":14}}}) : helper)))
    + "\r\n					</th>\r\n					<th scope=\"row\" class=\"subject\">\r\n						<a href=\"/keyword/keyword_base/"
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":95,"column":37},"end":{"line":95,"column":48}}}) : helper)))
    + "\" target=\"_blank\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":95,"column":66},"end":{"line":95,"column":77}}}) : helper)))
    + "</a>\r\n					</th>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"p_click_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":98,"column":6},"end":{"line":98,"column":40}}}))
    + "\r\n					</td>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"m_click_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":101,"column":6},"end":{"line":101,"column":40}}}))
    + "\r\n					</td>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"sum_click_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":104,"column":6},"end":{"line":104,"column":42}}}))
    + "\r\n					</td>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"shopping_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":107,"column":6},"end":{"line":107,"column":41}}}))
    + "\r\n					</td>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"toFixed")||(depth0 && lookupProperty(depth0,"toFixed"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rate") : depth0),{"name":"toFixed","hash":{},"data":data,"loc":{"start":{"line":110,"column":6},"end":{"line":110,"column":22}}}))
    + "\r\n					</td>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"toFixed")||(depth0 && lookupProperty(depth0,"toFixed"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"p_ave_ctr") : depth0),{"name":"toFixed","hash":{},"data":data,"loc":{"start":{"line":113,"column":6},"end":{"line":113,"column":27}}}))
    + "\r\n					</td>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"toFixed")||(depth0 && lookupProperty(depth0,"toFixed"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"m_ave_ctr") : depth0),{"name":"toFixed","hash":{},"data":data,"loc":{"start":{"line":116,"column":6},"end":{"line":116,"column":27}}}))
    + "\r\n					</td>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"p_ave_clk_cnt") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":119,"column":6},"end":{"line":119,"column":40}}}))
    + "\r\n					</td>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"m_ave_clk_cnt") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":122,"column":6},"end":{"line":122,"column":40}}}))
    + "\r\n					</td>\r\n					<td>\r\n						"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"avg_depth") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":125,"column":6},"end":{"line":125,"column":36}}}))
    + "\r\n					</td>\r\n				</tr>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<div class=\"utilities\">\r\n	<!-- \r\n	<button type=\"button\" class=\"aside set\" onclick=\"popup('#setItem')\">\r\n		항목 설정\r\n	</button>\r\n	--> \r\n</div>\r\n<div class=\"buttons\">\r\n	<button type=\"button\" class=\"aside excel\">\r\n		엑셀 다운로드\r\n	</button>\r\n	<button type=\"button\" class=\"aside expand\">\r\n		<span>\r\n			가로 확장\r\n		</span>\r\n	</button>\r\n</div>\r\n<div class=\"grid\">\r\n	<table style=\"min-width: 1500px;\" id=\"itemTable\">\r\n		<colgroup>\r\n			<col width=\"60\"></col>\r\n			<col width=\"250\"></col>\r\n		</colgroup>\r\n		<thead>\r\n			<tr>\r\n				<th scope=\"col\">\r\n					<button type=\"button\">\r\n						순위\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\" class=\"subject\">\r\n					<button type=\"button\">\r\n						키워드\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						PC 조회수\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						모바일 조회수\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						합계\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						상품수\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						경쟁도\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						PC클릭률\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						모바일클릭률\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						PC클릭수\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						모바일클릭수\r\n					</button>\r\n				</th>\r\n				<th scope=\"col\">\r\n					<button type=\"button\" class=\"sort\">\r\n						노출광고수\r\n					</button>\r\n				</th>\r\n			</tr>\r\n		</thead>\r\n		<tbody>\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"list") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":89,"column":3},"end":{"line":128,"column":12}}})) != null ? stack1 : "")
    + "		</tbody>\r\n	</table>\r\n</div>";
},"useData":true});
templates['keyword_analyze'] = template({"1":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "			<li>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"isAd") : depth0),"==",true,{"name":"ifCond","hash":{},"fn":container.program(2, data, 0),"inverse":container.program(4, data, 0),"data":data,"loc":{"start":{"line":54,"column":4},"end":{"line":58,"column":15}}})) != null ? stack1 : "")
    + "				<span>"
    + alias4(((helper = (helper = lookupProperty(helpers,"categoryName") || (depth0 != null ? lookupProperty(depth0,"categoryName") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"categoryName","hash":{},"data":data,"loc":{"start":{"line":59,"column":10},"end":{"line":59,"column":26}}}) : helper)))
    + "</span>\r\n				<strong><a href=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"link") || (depth0 != null ? lookupProperty(depth0,"link") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"link","hash":{},"data":data,"loc":{"start":{"line":60,"column":21},"end":{"line":60,"column":29}}}) : helper)))
    + "\" target=\"_blank\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"title") || (depth0 != null ? lookupProperty(depth0,"title") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"title","hash":{},"data":data,"loc":{"start":{"line":60,"column":47},"end":{"line":60,"column":56}}}) : helper)))
    + "</a></strong>\r\n				<dl class=\"type1\">\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rankingType") : depth0),"!=","L",{"name":"ifCond","hash":{},"fn":container.program(6, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":62,"column":5},"end":{"line":64,"column":16}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rankingType") : depth0),"==","N",{"name":"ifCond","hash":{},"fn":container.program(8, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":65,"column":5},"end":{"line":67,"column":16}}})) != null ? stack1 : "")
    + "					<dt>가격</dt><dd>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"price") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":68,"column":20},"end":{"line":68,"column":46}}}))
    + "원</dd>\r\n				</dl>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rankingType") : depth0),"==","L",{"name":"ifCond","hash":{},"fn":container.program(10, data, 0),"inverse":container.program(12, data, 0),"data":data,"loc":{"start":{"line":70,"column":4},"end":{"line":80,"column":15}}})) != null ? stack1 : "")
    + "				<dl class=\"type2\">\r\n					<dt>등록일</dt><dd>"
    + alias4(((helper = (helper = lookupProperty(helpers,"productDate") || (depth0 != null ? lookupProperty(depth0,"productDate") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"productDate","hash":{},"data":data,"loc":{"start":{"line":82,"column":21},"end":{"line":82,"column":36}}}) : helper)))
    + "</dd>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"reviewCount") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(23, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":83,"column":5},"end":{"line":85,"column":16}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"keepCount") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(25, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":86,"column":5},"end":{"line":88,"column":16}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"scoreInfo") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(27, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":89,"column":5},"end":{"line":91,"column":16}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"mallCount") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(29, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":92,"column":5},"end":{"line":94,"column":16}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"purchaseCount") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(31, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":95,"column":5},"end":{"line":97,"column":16}}})) != null ? stack1 : "")
    + "				</dl>\r\n				<div class=\"thumb\" style=\"background-image: url('"
    + alias4(((helper = (helper = lookupProperty(helpers,"img") || (depth0 != null ? lookupProperty(depth0,"img") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"img","hash":{},"data":data,"loc":{"start":{"line":99,"column":53},"end":{"line":99,"column":60}}}) : helper)))
    + "');\"> <span>썸네일</span></div>\r\n			</li>\r\n";
},"2":function(container,depth0,helpers,partials,data) {
    return "					<em>광고</em>\r\n";
},"4":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "					<em>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"ranking") || (depth0 != null ? lookupProperty(depth0,"ranking") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"ranking","hash":{},"data":data,"loc":{"start":{"line":57,"column":9},"end":{"line":57,"column":20}}}) : helper)))
    + "</em>\r\n";
},"6":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<dt>상점명</dt><dd>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"mallName") || (depth0 != null ? lookupProperty(depth0,"mallName") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"mallName","hash":{},"data":data,"loc":{"start":{"line":63,"column":22},"end":{"line":63,"column":34}}}) : helper)))
    + "</dd>\r\n";
},"8":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<dt>상점레벨</dt><dd>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"mallGrade") || (depth0 != null ? lookupProperty(depth0,"mallGrade") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"mallGrade","hash":{},"data":data,"loc":{"start":{"line":66,"column":23},"end":{"line":66,"column":36}}}) : helper)))
    + "</dd>\r\n";
},"10":function(container,depth0,helpers,partials,data) {
    return "					<b class=\"type1\">가격비교</b>\r\n";
},"12":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"rankingType") : depth0),"==","H",{"name":"ifCond","hash":{},"fn":container.program(13, data, 0),"inverse":container.program(15, data, 0),"data":data,"loc":{"start":{"line":72,"column":4},"end":{"line":80,"column":4}}})) != null ? stack1 : "");
},"13":function(container,depth0,helpers,partials,data) {
    return "					<b class=\"type2\">핫딜</b>\r\n";
},"15":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"rankingType") : depth0),"==","N",{"name":"ifCond","hash":{},"fn":container.program(16, data, 0),"inverse":container.program(18, data, 0),"data":data,"loc":{"start":{"line":74,"column":4},"end":{"line":80,"column":4}}})) != null ? stack1 : "");
},"16":function(container,depth0,helpers,partials,data) {
    return "					<b class=\"type3\">스마트스토어</b>\r\n";
},"18":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"rankingType") : depth0),"==","W",{"name":"ifCond","hash":{},"fn":container.program(19, data, 0),"inverse":container.program(21, data, 0),"data":data,"loc":{"start":{"line":76,"column":4},"end":{"line":80,"column":4}}})) != null ? stack1 : "");
},"19":function(container,depth0,helpers,partials,data) {
    return "					<b class=\"type4\">윈도</b>	\r\n";
},"21":function(container,depth0,helpers,partials,data) {
    return "					<b class=\"type5\">자사몰</b>\r\n				";
},"23":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<dt>리뷰</dt><dd>"
    + container.escapeExpression((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"reviewCount") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":84,"column":21},"end":{"line":84,"column":53}}}))
    + "</dd>\r\n";
},"25":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<dt>찜</dt><dd>"
    + container.escapeExpression((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"keepCount") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":87,"column":20},"end":{"line":87,"column":50}}}))
    + "</dd>\r\n";
},"27":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<dt>평점</dt><dd>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"scoreInfo") || (depth0 != null ? lookupProperty(depth0,"scoreInfo") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"scoreInfo","hash":{},"data":data,"loc":{"start":{"line":90,"column":21},"end":{"line":90,"column":34}}}) : helper)))
    + "</dd>\r\n";
},"29":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<dt>판매처</dt><dd>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"mallCount") || (depth0 != null ? lookupProperty(depth0,"mallCount") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"mallCount","hash":{},"data":data,"loc":{"start":{"line":93,"column":22},"end":{"line":93,"column":35}}}) : helper)))
    + "</dd>\r\n";
},"31":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<dt>6개월판매량</dt><dd>"
    + container.escapeExpression((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"purchaseCount") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":96,"column":25},"end":{"line":96,"column":59}}}))
    + "</dd>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<!-- 상위 노출상품 분석 -->\r\n<h3 class=\"hidden\">상위 노출상품 분석</h3>\r\n\r\n<!-- 판매 분석 -->\r\n<section class=\"analysis\">\r\n	<header>\r\n		<h4 class=\"title\">판매 분석</h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca81139553cf791c6d7468#2563a1f718ca81e7a5fdc88bd5f68cfc')\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 415px;\">\r\n						조회한 키워드의 상위 40개 상품 판매량·판매금액을 집계한 지표입니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>   \r\n		</div>\r\n	</header>\r\n	<ul class=\"analysisContent\">\r\n		<li class=\"type1\">\r\n			<span class=\"title\">상위 40개 총 판매량(6개월.추정)</span>\r\n			<p><em>"
    + alias3((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"sumPurchaseCount") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":21,"column":10},"end":{"line":21,"column":47}}}))
    + "</em>개</p>\r\n		</li>\r\n		<li class=\"type1\">\r\n			<span class=\"title\">상위 40개 판매금액(6개월.추정)</span>\r\n			<p><em>"
    + alias3((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"sumSales") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":25,"column":10},"end":{"line":25,"column":39}}}))
    + "</em>원</p>\r\n		</li>\r\n		\r\n	</ul>\r\n</section>\r\n<!-- //판매 분석 -->\r\n\r\n<!-- 상위 노출 상품 -->\r\n<section class=\"analysis case\">\r\n	<header>\r\n		<h4 class=\"title\">상위 노출 상품</h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca81139553cf791c6d7468#2563a1f718ca816ea3c3f240fb41a92c')\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 465px;\">\r\n						네이버 쇼핑 1페이지에 노출된 상위 40개 상품의 상세 정보를 확인할 수 있습니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>\r\n		</div>\r\n		<div class=\"buttons\">\r\n			<button type=\"button\" class=\"aside excel\" id=\"btnAnalyzeExcel\">엑셀 다운로드</button>\r\n		</div>\r\n	</header>\r\n\r\n	<ul class=\"listProducts\">\r\n		<!-- item -->\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"productList") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":52,"column":2},"end":{"line":101,"column":11}}})) != null ? stack1 : "")
    + "		<!-- //item -->\r\n\r\n		\r\n	</ul>\r\n</section>\r\n<!-- //상위 노출 상품 -->";
},"useData":true});
templates['keyword_analyze_coupang'] = template({"1":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "			<li class=\"type1\">\r\n				<span class=\"title\">1개월 조회수</span>\r\n				<p><em>"
    + container.escapeExpression((lookupProperty(helpers,"qcSummary")||(depth0 && lookupProperty(depth0,"qcSummary"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"qc") : depth0),{"name":"qcSummary","hash":{},"data":data,"loc":{"start":{"line":23,"column":11},"end":{"line":23,"column":27}}}))
    + "</em></p>\r\n			</li>\r\n";
},"3":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "		<li class=\"type1\">\r\n			<span class=\"title\">상위 "
    + alias4(((helper = (helper = lookupProperty(helpers,"productCount") || (depth0 != null ? lookupProperty(depth0,"productCount") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"productCount","hash":{},"data":data,"loc":{"start":{"line":28,"column":26},"end":{"line":28,"column":42}}}) : helper)))
    + "개 총 판매량(1개월)</span>\r\n			<p><em>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"sumPurchaseCount") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":29,"column":10},"end":{"line":29,"column":47}}}))
    + "</em>개</p>\r\n		</li>\r\n		<li class=\"type1\">\r\n			<span class=\"title\">상위 "
    + alias4(((helper = (helper = lookupProperty(helpers,"productCount") || (depth0 != null ? lookupProperty(depth0,"productCount") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"productCount","hash":{},"data":data,"loc":{"start":{"line":32,"column":26},"end":{"line":32,"column":42}}}) : helper)))
    + "개 총 판매금액(1개월)</span>\r\n			<p><em>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"sumSales") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":33,"column":10},"end":{"line":33,"column":39}}}))
    + "</em>원</p>\r\n		</li>\r\n";
},"5":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"productList") : depth0)) != null ? lookupProperty(stack1,"length") : stack1),">",0,{"name":"ifCond","hash":{},"fn":container.program(6, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":46,"column":1},"end":{"line":110,"column":12}}})) != null ? stack1 : "");
},"6":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "	<section class=\"analysis case\">\r\n		<header>\r\n			<h4 class=\"title\">상위 노출 상품(쿠팡 랭킹순)</h4>\r\n			<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/25e3a1f718ca80559e90e09cce93a531#2993a1f718ca80239038edf2e7777679')\">\r\n				<button type=\"button\"><span>도움말 보기</span></button>\r\n				<div style=\"left: -40px; width: 545px;\">\r\n							쿠팡 검색결과 1페이지의 실제 노출 순서(랭킹)를 기준으로 상위 40개 상품 데이터를 제공합니다.\r\n							<a href=\"\">\r\n								[더 알아보기]\r\n							</a>  \r\n				</div>\r\n			</div>\r\n			\r\n			<div class=\"buttons\">\r\n				<button type=\"button\" class=\"aside excel\" id=\"btnAnalyzeCoupangExcel\">엑셀 다운로드</button>\r\n			</div>\r\n		</header>\r\n		<ul class=\"listProducts\">\r\n			<!-- item -->\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"productList") : depth0),{"name":"each","hash":{},"fn":container.program(7, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":66,"column":3},"end":{"line":106,"column":12}}})) != null ? stack1 : "")
    + "			<!-- //item -->		\r\n		</ul>\r\n	</section>\r\n";
},"7":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<li>\r\n					\r\n					<em>"
    + alias4(((helper = (helper = lookupProperty(helpers,"ranking") || (depth0 != null ? lookupProperty(depth0,"ranking") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"ranking","hash":{},"data":data,"loc":{"start":{"line":69,"column":9},"end":{"line":69,"column":20}}}) : helper)))
    + "</em>\r\n					\r\n					<span>"
    + alias4(((helper = (helper = lookupProperty(helpers,"category") || (depth0 != null ? lookupProperty(depth0,"category") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"category","hash":{},"data":data,"loc":{"start":{"line":71,"column":11},"end":{"line":71,"column":23}}}) : helper)))
    + "</span>\r\n					<strong><a href=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"link") || (depth0 != null ? lookupProperty(depth0,"link") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"link","hash":{},"data":data,"loc":{"start":{"line":72,"column":22},"end":{"line":72,"column":30}}}) : helper)))
    + "\" target=\"_blank\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"productName") || (depth0 != null ? lookupProperty(depth0,"productName") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"productName","hash":{},"data":data,"loc":{"start":{"line":72,"column":48},"end":{"line":72,"column":63}}}) : helper)))
    + "</a></strong>\r\n					<dl class=\"type1\">\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"brandName") : depth0),"!=","",{"name":"ifCond","hash":{},"fn":container.program(8, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":74,"column":6},"end":{"line":76,"column":17}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"manufacture") : depth0),"!=","",{"name":"ifCond","hash":{},"fn":container.program(10, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":77,"column":6},"end":{"line":79,"column":17}}})) != null ? stack1 : "")
    + "						<dt>가격</dt><dd>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"salePrice") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":80,"column":21},"end":{"line":80,"column":51}}}))
    + "원</dd>\r\n					</dl>\r\n					\r\n					<!-- <b class=\"type1\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"itemId") || (depth0 != null ? lookupProperty(depth0,"itemId") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"itemId","hash":{},"data":data,"loc":{"start":{"line":83,"column":27},"end":{"line":83,"column":37}}}) : helper)))
    + "</b> -->\r\n					\r\n					<dl class=\"type2\">\r\n						\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"ratingCount") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(12, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":87,"column":6},"end":{"line":89,"column":17}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"pvLast28Day") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(14, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":90,"column":6},"end":{"line":92,"column":17}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"salesLast28d") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(16, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":93,"column":6},"end":{"line":96,"column":17}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"salesLast28dAmount") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(18, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":97,"column":6},"end":{"line":99,"column":17}}})) != null ? stack1 : "")
    + "					</dl>\r\n					<div class=\"utilities\">\r\n						<a class=\"primaryMedium btnShowKeyword\" data-category-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"categoryCode") || (depth0 != null ? lookupProperty(depth0,"categoryCode") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"categoryCode","hash":{},"data":data,"loc":{"start":{"line":102,"column":64},"end":{"line":102,"column":80}}}) : helper)))
    + "\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"itemId") || (depth0 != null ? lookupProperty(depth0,"itemId") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"itemId","hash":{},"data":data,"loc":{"start":{"line":102,"column":91},"end":{"line":102,"column":101}}}) : helper)))
    + "\"><span>키워드</span></a>\r\n	            	</div>\r\n					<div class=\"thumb\" style=\"background-image: url('"
    + alias4(((helper = (helper = lookupProperty(helpers,"imagePath") || (depth0 != null ? lookupProperty(depth0,"imagePath") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"imagePath","hash":{},"data":data,"loc":{"start":{"line":104,"column":54},"end":{"line":104,"column":67}}}) : helper)))
    + "');\"> <span>썸네일</span></div>\r\n				</li>\r\n";
},"8":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "							<dt>브랜드</dt><dd>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"brandName") || (depth0 != null ? lookupProperty(depth0,"brandName") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"brandName","hash":{},"data":data,"loc":{"start":{"line":75,"column":23},"end":{"line":75,"column":36}}}) : helper)))
    + "</dd>\r\n";
},"10":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "							<dt>제조사</dt><dd>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"manufacture") || (depth0 != null ? lookupProperty(depth0,"manufacture") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"manufacture","hash":{},"data":data,"loc":{"start":{"line":78,"column":23},"end":{"line":78,"column":38}}}) : helper)))
    + "</dd>\r\n";
},"12":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "							<dt>리뷰</dt><dd>"
    + container.escapeExpression((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"ratingCount") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":88,"column":22},"end":{"line":88,"column":54}}}))
    + "</dd>\r\n";
},"14":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "							<dt>클릭수</dt><dd>"
    + container.escapeExpression((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"pvLast28Day") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":91,"column":23},"end":{"line":91,"column":55}}}))
    + "</dd>\r\n";
},"16":function(container,depth0,helpers,partials,data) {
    var alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "							<dt>판매량</dt><dd>"
    + alias3((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"salesLast28d") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":94,"column":23},"end":{"line":94,"column":56}}}))
    + "</dd>\r\n							<dt>전환율</dt><dd>"
    + alias3((lookupProperty(helpers,"toFixed1")||(depth0 && lookupProperty(depth0,"toFixed1"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"cvr") : depth0),{"name":"toFixed1","hash":{},"data":data,"loc":{"start":{"line":95,"column":23},"end":{"line":95,"column":40}}}))
    + "%</dd>\r\n";
},"18":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "							<dt>1개월 판매금액</dt><dd>"
    + container.escapeExpression((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"salesLast28dAmount") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":98,"column":28},"end":{"line":98,"column":67}}}))
    + "</dd>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<!-- 상위 노출상품 분석 -->\r\n<h3 class=\"hidden\">상위 노출상품 분석(쿠팡)</h3>\r\n\r\n<!-- 판매 분석 -->\r\n<section class=\"analysis\" style=\"border-top:unset;\">\r\n	<header>\r\n		<h4 class=\"title\">조회수&판매분석</h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/25e3a1f718ca80559e90e09cce93a531#2993a1f718ca8011a20ce13f9e3958bd')\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 475px;\">\r\n						최근 1개월간 조회수·판매량·판매금액을 기준으로 시장 규모를 확인할 수 있습니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>\r\n		</div>\r\n	</header>\r\n	\r\n	<ul class=\"analysisContent\">\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"qc") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":20,"column":2},"end":{"line":25,"column":13}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"isMoreCategory") : depth0),"==",false,{"name":"ifCond","hash":{},"fn":container.program(3, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":26,"column":2},"end":{"line":35,"column":13}}})) != null ? stack1 : "")
    + "	</ul>\r\n	\r\n</section>\r\n<!-- 카테고리 분석 -->\r\n<div id=\"coupangCategoryDIV\"></div>\r\n<!-- //카테고리 분석 -->\r\n<!-- //판매 분석 -->\r\n<div id=\"topProductDIV\"></div>\r\n\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"isMoreCategory") : depth0),"==",false,{"name":"ifCond","hash":{},"fn":container.program(5, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":45,"column":0},"end":{"line":111,"column":11}}})) != null ? stack1 : "");
},"useData":true});
templates['keyword_analyze_coupang_category'] = template({"1":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "	<ul class=\"analysisContent categoriesDIVOrigin\">\r\n		<li class=\"\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"categoryList") : depth0),{"name":"each","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":18,"column":3},"end":{"line":22,"column":12}}})) != null ? stack1 : "")
    + "		</li>\r\n	</ul>\r\n	<header>\r\n		<div id=\"btnMoreCategory\">\r\n			+더보기\r\n		</div>\r\n	</header>\r\n";
},"2":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<p>\r\n					"
    + alias3(((helper = (helper = lookupProperty(helpers,"categoryName") || (depth0 != null ? lookupProperty(depth0,"categoryName") : depth0)) != null ? helper : alias2),(typeof helper === "function" ? helper.call(alias1,{"name":"categoryName","hash":{},"data":data,"loc":{"start":{"line":20,"column":5},"end":{"line":20,"column":21}}}) : helper)))
    + "<span style=\"color:red;\">("
    + alias3((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rate") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":20,"column":47},"end":{"line":20,"column":72}}}))
    + "%)</span>\r\n				</p>\r\n";
},"4":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "		<ul class=\"analysisContent\">\r\n			<li>\r\n				<li class=\"\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"moreCategoryList") : depth0),{"name":"each","hash":{},"fn":container.program(5, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":36,"column":5},"end":{"line":40,"column":14}}})) != null ? stack1 : "")
    + "				</li>\r\n								\r\n			</li>\r\n		</ul>\r\n";
},"5":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<p class=\"btnChangeCategory\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"DisplayItemCategoryCode") || (depth0 != null ? lookupProperty(depth0,"DisplayItemCategoryCode") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"DisplayItemCategoryCode","hash":{},"data":data,"loc":{"start":{"line":37,"column":44},"end":{"line":37,"column":71}}}) : helper)))
    + "\">\r\n							"
    + alias4(((helper = (helper = lookupProperty(helpers,"CategoryPath") || (depth0 != null ? lookupProperty(depth0,"CategoryPath") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"CategoryPath","hash":{},"data":data,"loc":{"start":{"line":38,"column":7},"end":{"line":38,"column":23}}}) : helper)))
    + "\r\n						</p>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<section class=\"analysis\" style=\"border-top:0px !important;\">\r\n	<header>\r\n		<h4 class=\"title\">카테고리</h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/25e3a1f718ca80559e90e09cce93a531#2993a1f718ca8024a571e8dfa81bb37a')\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 490px;\">\r\n						조회한 키워드가 쿠팡 내 어떤 카테고리에 집중 노출되는지 비율로 확인할 수 있습니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>   \r\n		</div>\r\n	</header>\r\n	\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"isMoreCategory") : depth0),"==",false,{"name":"ifCond","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":15,"column":1},"end":{"line":30,"column":12}}})) != null ? stack1 : "")
    + "	\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"isMoreCategory") : depth0),"==",true,{"name":"ifCond","hash":{},"fn":container.program(4, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":32,"column":1},"end":{"line":45,"column":12}}})) != null ? stack1 : "")
    + "</section>";
},"useData":true});
templates['keyword_analyze_coupang_topproduct'] = template({"1":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"topProductList") : depth0)) != null ? lookupProperty(stack1,"length") : stack1),">",0,{"name":"ifCond","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":3,"column":1},"end":{"line":60,"column":12}}})) != null ? stack1 : "");
},"2":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "		<section class=\"analysis case\">\r\n			<header>\r\n				<h4 class=\"title\">상위 노출 상품</h4>\r\n				<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/25e3a1f718ca80559e90e09cce93a531#25e3a1f718ca819bb0bcfd2f5a1b5555')\">\r\n					<button type=\"button\"><span>도움말 보기</span></button>\r\n					<div style=\"left: -40px; width: 490px;\">\r\n								최근 30일간 매출 기준 상위 20개 상품의 판매성과와 광고 비중을 비교할 수 있습니다.\r\n								<a href=\"\">\r\n									[더 알아보기]\r\n								</a>  \r\n					</div>\r\n				</div>\r\n				\r\n				<a class=\"btnChangeSort\" data-type=\"pv\">클릭순</a>\r\n				<a class=\"btnChangeSort\" data-type=\"ctr\">클릭율순</a>\r\n				<a class=\"btnChangeSort\" data-type=\"sales\">매출순</a>\r\n				<a class=\"btnChangeSort\" data-type=\"ad\">광고비중순</a>\r\n				\r\n				<div class=\"buttons\">\r\n					<button type=\"button\" class=\"aside excel\" id=\"btnAnalyzeCoupangExcel2\">엑셀 다운로드</button>\r\n				</div>\r\n			</header>\r\n			\r\n			<ul class=\"listProducts\">\r\n				<!-- item -->\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"topProductList") : depth0),{"name":"each","hash":{},"fn":container.program(3, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":29,"column":4},"end":{"line":56,"column":13}}})) != null ? stack1 : "")
    + "				<!-- //item -->		\r\n			</ul>\r\n		</section>\r\n";
},"3":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3=container.escapeExpression, alias4="function", lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "					<li>\r\n						\r\n						<em>"
    + alias3((lookupProperty(helpers,"inc")||(depth0 && lookupProperty(depth0,"inc"))||alias2).call(alias1,(data && lookupProperty(data,"index")),{"name":"inc","hash":{},"data":data,"loc":{"start":{"line":32,"column":10},"end":{"line":32,"column":24}}}))
    + "</em>\r\n						\r\n						<span>"
    + alias3(container.lambda(((stack1 = (data && lookupProperty(data,"root"))) && lookupProperty(stack1,"mainCategory")), depth0))
    + "</span>\r\n						<strong><a href=\"https://www.coupang.com/vp/products/"
    + alias3(((helper = (helper = lookupProperty(helpers,"pid") || (depth0 != null ? lookupProperty(depth0,"pid") : depth0)) != null ? helper : alias2),(typeof helper === alias4 ? helper.call(alias1,{"name":"pid","hash":{},"data":data,"loc":{"start":{"line":35,"column":59},"end":{"line":35,"column":66}}}) : helper)))
    + "?vendorItemId="
    + alias3(((helper = (helper = lookupProperty(helpers,"vid") || (depth0 != null ? lookupProperty(depth0,"vid") : depth0)) != null ? helper : alias2),(typeof helper === alias4 ? helper.call(alias1,{"name":"vid","hash":{},"data":data,"loc":{"start":{"line":35,"column":80},"end":{"line":35,"column":87}}}) : helper)))
    + "\" target=\"_blank\">"
    + alias3(((helper = (helper = lookupProperty(helpers,"name") || (depth0 != null ? lookupProperty(depth0,"name") : depth0)) != null ? helper : alias2),(typeof helper === alias4 ? helper.call(alias1,{"name":"name","hash":{},"data":data,"loc":{"start":{"line":35,"column":105},"end":{"line":35,"column":113}}}) : helper)))
    + " "
    + alias3(((helper = (helper = lookupProperty(helpers,"option") || (depth0 != null ? lookupProperty(depth0,"option") : depth0)) != null ? helper : alias2),(typeof helper === alias4 ? helper.call(alias1,{"name":"option","hash":{},"data":data,"loc":{"start":{"line":35,"column":114},"end":{"line":35,"column":124}}}) : helper)))
    + "</a></strong>\r\n						<dl class=\"type1\">\r\n							<dt>가격</dt><dd>"
    + alias3((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"price") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":37,"column":22},"end":{"line":37,"column":48}}}))
    + "원</dd>\r\n							<dt>리뷰</dt><dd>"
    + alias3((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"review") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":38,"column":22},"end":{"line":38,"column":49}}}))
    + "("
    + alias3(((helper = (helper = lookupProperty(helpers,"score") || (depth0 != null ? lookupProperty(depth0,"score") : depth0)) != null ? helper : alias2),(typeof helper === alias4 ? helper.call(alias1,{"name":"score","hash":{},"data":data,"loc":{"start":{"line":38,"column":50},"end":{"line":38,"column":59}}}) : helper)))
    + ")</dd>\r\n						</dl>\r\n						\r\n						<!-- <b class=\"type1\">"
    + alias3(((helper = (helper = lookupProperty(helpers,"itemId") || (depth0 != null ? lookupProperty(depth0,"itemId") : depth0)) != null ? helper : alias2),(typeof helper === alias4 ? helper.call(alias1,{"name":"itemId","hash":{},"data":data,"loc":{"start":{"line":41,"column":28},"end":{"line":41,"column":38}}}) : helper)))
    + "</b> -->\r\n						\r\n						<dl class=\"type2\">\r\n							<dt>노출증가</dt><dd>"
    + alias3((lookupProperty(helpers,"toFixed1")||(depth0 && lookupProperty(depth0,"toFixed1"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"impressionRate") : depth0),{"name":"toFixed1","hash":{},"data":data,"loc":{"start":{"line":44,"column":24},"end":{"line":44,"column":51}}}))
    + "%</dd>\r\n							<dt>클릭수</dt><dd>"
    + alias3((lookupProperty(helpers,"pvSummary")||(depth0 && lookupProperty(depth0,"pvSummary"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"pv") : depth0),{"name":"pvSummary","hash":{},"data":data,"loc":{"start":{"line":45,"column":23},"end":{"line":45,"column":40}}}))
    + "("
    + alias3((lookupProperty(helpers,"toFixed1")||(depth0 && lookupProperty(depth0,"toFixed1"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"pvRate") : depth0),{"name":"toFixed1","hash":{},"data":data,"loc":{"start":{"line":45,"column":41},"end":{"line":45,"column":60}}}))
    + "%)</dd>\r\n							<dt>클릭율</dt><dd>"
    + alias3((lookupProperty(helpers,"toFixed1")||(depth0 && lookupProperty(depth0,"toFixed1"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"ctr") : depth0),{"name":"toFixed1","hash":{},"data":data,"loc":{"start":{"line":46,"column":23},"end":{"line":46,"column":39}}}))
    + "%</dd>\r\n							<dt>광고비중</dt><dd>"
    + alias3((lookupProperty(helpers,"toFixed1")||(depth0 && lookupProperty(depth0,"toFixed1"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"adImpressionWeight") : depth0),{"name":"toFixed1","hash":{},"data":data,"loc":{"start":{"line":47,"column":24},"end":{"line":47,"column":55}}}))
    + "%</dd>\r\n						</dl>\r\n						\r\n						<div class=\"utilities\">\r\n							<a class=\"primaryMedium btnShowKeyword\" data-id=\""
    + alias3(((helper = (helper = lookupProperty(helpers,"id") || (depth0 != null ? lookupProperty(depth0,"id") : depth0)) != null ? helper : alias2),(typeof helper === alias4 ? helper.call(alias1,{"name":"id","hash":{},"data":data,"loc":{"start":{"line":51,"column":56},"end":{"line":51,"column":62}}}) : helper)))
    + "\"><span>키워드</span></a>\r\n		            	</div>\r\n						\r\n						<div class=\"thumb\" style=\"background-image: url('https://thumbnail14.coupangcdn.com/thumbnails/remote/250x250ex/image/"
    + alias3(((helper = (helper = lookupProperty(helpers,"img") || (depth0 != null ? lookupProperty(depth0,"img") : depth0)) != null ? helper : alias2),(typeof helper === alias4 ? helper.call(alias1,{"name":"img","hash":{},"data":data,"loc":{"start":{"line":54,"column":124},"end":{"line":54,"column":131}}}) : helper)))
    + "');\"> <span>썸네일</span></div>\r\n					</li>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<!-- 상위 노출 상품 -->\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"topProductList") : depth0),"!=",null,{"name":"ifCond","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":2,"column":0},"end":{"line":61,"column":11}}})) != null ? stack1 : "");
},"useData":true});
templates['keyword_base'] = template({"1":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=container.lambda, alias2=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "			<p>"
    + alias2(alias1(((stack1 = ((stack1 = (depth0 != null ? lookupProperty(depth0,"categoryList") : depth0)) != null ? lookupProperty(stack1,"0") : stack1)) != null ? lookupProperty(stack1,"categoryName") : stack1), depth0))
    + " ("
    + alias2(alias1(((stack1 = ((stack1 = (depth0 != null ? lookupProperty(depth0,"categoryList") : depth0)) != null ? lookupProperty(stack1,"0") : stack1)) != null ? lookupProperty(stack1,"categoryCountRate") : stack1), depth0))
    + "%)</p>\r\n";
},"3":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "			<ul class>\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"categoryList") : depth0),{"name":"each","hash":{},"fn":container.program(4, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":12,"column":4},"end":{"line":16,"column":13}}})) != null ? stack1 : "")
    + "			</ul>\r\n			<button type=\"button\" onclick=\"$(this).parent('.categories').toggleClass('showing');\"><span>더보기</span></button>	\r\n";
},"4":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = lookupProperty(helpers,"if").call(depth0 != null ? depth0 : (container.nullContext || {}),(data && lookupProperty(data,"index")),{"name":"if","hash":{},"fn":container.program(5, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":13,"column":5},"end":{"line":15,"column":12}}})) != null ? stack1 : "");
},"5":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<li>"
    + alias4(((helper = (helper = lookupProperty(helpers,"categoryName") || (depth0 != null ? lookupProperty(depth0,"categoryName") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"categoryName","hash":{},"data":data,"loc":{"start":{"line":14,"column":10},"end":{"line":14,"column":26}}}) : helper)))
    + " ("
    + alias4(((helper = (helper = lookupProperty(helpers,"categoryCountRate") || (depth0 != null ? lookupProperty(depth0,"categoryCountRate") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"categoryCountRate","hash":{},"data":data,"loc":{"start":{"line":14,"column":28},"end":{"line":14,"column":49}}}) : helper)))
    + "%)</li>\r\n";
},"7":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<p class=\"worst\">\r\n					<em>"
    + container.escapeExpression((lookupProperty(helpers,"parseFloat")||(depth0 && lookupProperty(depth0,"parseFloat"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"rate") : stack1),{"name":"parseFloat","hash":{},"data":data,"loc":{"start":{"line":93,"column":9},"end":{"line":93,"column":37}}}))
    + "</em>\r\n				</p>\r\n";
},"9":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"rate") : stack1),">",90,{"name":"ifCond","hash":{},"fn":container.program(10, data, 0),"inverse":container.program(12, data, 0),"data":data,"loc":{"start":{"line":95,"column":3},"end":{"line":111,"column":3}}})) != null ? stack1 : "");
},"10":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<p class=\"negative\">\r\n					<em>"
    + container.escapeExpression((lookupProperty(helpers,"parseFloat")||(depth0 && lookupProperty(depth0,"parseFloat"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"rate") : stack1),{"name":"parseFloat","hash":{},"data":data,"loc":{"start":{"line":97,"column":9},"end":{"line":97,"column":37}}}))
    + "</em>\r\n				</p>\r\n";
},"12":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"rate") : stack1),">",80,{"name":"ifCond","hash":{},"fn":container.program(13, data, 0),"inverse":container.program(15, data, 0),"data":data,"loc":{"start":{"line":99,"column":3},"end":{"line":111,"column":3}}})) != null ? stack1 : "");
},"13":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<p class=\"normal\">\r\n					<em>"
    + container.escapeExpression((lookupProperty(helpers,"parseFloat")||(depth0 && lookupProperty(depth0,"parseFloat"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"rate") : stack1),{"name":"parseFloat","hash":{},"data":data,"loc":{"start":{"line":101,"column":9},"end":{"line":101,"column":37}}}))
    + "</em>\r\n				</p>\r\n";
},"15":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"rate") : stack1),">",70,{"name":"ifCond","hash":{},"fn":container.program(16, data, 0),"inverse":container.program(18, data, 0),"data":data,"loc":{"start":{"line":103,"column":3},"end":{"line":111,"column":3}}})) != null ? stack1 : "");
},"16":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<p class=\"positive\">\r\n					<em>"
    + container.escapeExpression((lookupProperty(helpers,"parseFloat")||(depth0 && lookupProperty(depth0,"parseFloat"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"rate") : stack1),{"name":"parseFloat","hash":{},"data":data,"loc":{"start":{"line":105,"column":9},"end":{"line":105,"column":37}}}))
    + "</em>\r\n				</p>\r\n";
},"18":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<p class=\"best\">\r\n					<em>"
    + container.escapeExpression((lookupProperty(helpers,"parseFloat")||(depth0 && lookupProperty(depth0,"parseFloat"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"rate") : stack1),{"name":"parseFloat","hash":{},"data":data,"loc":{"start":{"line":109,"column":9},"end":{"line":109,"column":37}}}))
    + "</em>\r\n				</p>	\r\n			";
},"20":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"contains")||(depth0 && lookupProperty(depth0,"contains"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),depth0,"쇼핑",{"name":"contains","hash":{},"fn":container.program(21, data, 0),"inverse":container.program(23, data, 0),"data":data,"loc":{"start":{"line":160,"column":6},"end":{"line":164,"column":19}}})) != null ? stack1 : "");
},"21":function(container,depth0,helpers,partials,data) {
    return "							<span class=\"selected\">"
    + container.escapeExpression(container.lambda(depth0, depth0))
    + "</span>\r\n";
},"23":function(container,depth0,helpers,partials,data) {
    return "							<span>"
    + container.escapeExpression(container.lambda(depth0, depth0))
    + "</span>\r\n";
},"25":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=depth0 != null ? depth0 : (container.nullContext || {}), lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = lookupProperty(helpers,"if").call(alias1,(lookupProperty(helpers,"contains2")||(depth0 && lookupProperty(depth0,"contains2"))||container.hooks.helperMissing).call(alias1,depth0,"쇼핑",{"name":"contains2","hash":{},"data":data,"loc":{"start":{"line":178,"column":12},"end":{"line":178,"column":33}}}),{"name":"if","hash":{},"fn":container.program(21, data, 0),"inverse":container.program(26, data, 0),"data":data,"loc":{"start":{"line":178,"column":6},"end":{"line":186,"column":13}}})) != null ? stack1 : "");
},"26":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=depth0 != null ? depth0 : (container.nullContext || {}), lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = lookupProperty(helpers,"if").call(alias1,(lookupProperty(helpers,"contains2")||(depth0 && lookupProperty(depth0,"contains2"))||container.hooks.helperMissing).call(alias1,depth0,"네이버 가격비교",{"name":"contains2","hash":{},"data":data,"loc":{"start":{"line":180,"column":16},"end":{"line":180,"column":43}}}),{"name":"if","hash":{},"fn":container.program(21, data, 0),"inverse":container.program(27, data, 0),"data":data,"loc":{"start":{"line":180,"column":6},"end":{"line":186,"column":6}}})) != null ? stack1 : "");
},"27":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=depth0 != null ? depth0 : (container.nullContext || {}), lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = lookupProperty(helpers,"if").call(alias1,(lookupProperty(helpers,"contains2")||(depth0 && lookupProperty(depth0,"contains2"))||container.hooks.helperMissing).call(alias1,depth0,"네이버플러스 스토어",{"name":"contains2","hash":{},"data":data,"loc":{"start":{"line":182,"column":16},"end":{"line":182,"column":45}}}),{"name":"if","hash":{},"fn":container.program(21, data, 0),"inverse":container.program(28, data, 0),"data":data,"loc":{"start":{"line":182,"column":6},"end":{"line":186,"column":6}}})) != null ? stack1 : "");
},"28":function(container,depth0,helpers,partials,data) {
    return "							<span>"
    + container.escapeExpression(container.lambda(depth0, depth0))
    + "</span>\r\n						";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=container.lambda, alias2=container.escapeExpression, alias3=depth0 != null ? depth0 : (container.nullContext || {}), alias4=container.hooks.helperMissing, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<!-- 종합분석 -->\r\n<!-- Header -->\r\n<header class=\"analysisHeader\">\r\n	<h3 class=\"title\">"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + " <span class=\"hidden\">종합 분석</span></h3>\r\n	<div class=\"thumb\" style=\"background-image: url("
    + alias2(((helper = (helper = lookupProperty(helpers,"productimg") || (depth0 != null ? lookupProperty(depth0,"productimg") : depth0)) != null ? helper : alias4),(typeof helper === "function" ? helper.call(alias3,{"name":"productimg","hash":{},"data":data,"loc":{"start":{"line":5,"column":49},"end":{"line":5,"column":63}}}) : helper)))
    + ");\"><span>이미지</span></div>\r\n	<div class=\"categories\">\r\n"
    + ((stack1 = lookupProperty(helpers,"if").call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"categoryList") : depth0)) != null ? lookupProperty(stack1,"0") : stack1),{"name":"if","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":7,"column":2},"end":{"line":9,"column":9}}})) != null ? stack1 : "")
    + ((stack1 = lookupProperty(helpers,"if").call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"categoryList") : depth0)) != null ? lookupProperty(stack1,"1") : stack1),{"name":"if","hash":{},"fn":container.program(3, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":10,"column":2},"end":{"line":19,"column":9}}})) != null ? stack1 : "")
    + "	</div>\r\n	<dl>\r\n		<dt>도매검색</dt>\r\n		<dd>\r\n			<p><a href=\"#\" class=\"btn1688\" data-keyword=\""
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\"><img src=\"/assets/images/logos/1688.png\" alt=\"1688\"></a></p>\r\n			<p><a href=\"https://ko.aliexpress.com/w/wholesale-"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + ".html\" target=\"_blank\"><img src=\"/assets/images/logos/aliexpress.png\" alt=\"Ali Express\"></a></p>\r\n		</dd>\r\n		<dt>쇼핑검색</dt>\r\n		<dd>\r\n			<p>\r\n				<a href=\"https://search.shopping.naver.com/search/all?query="
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\" target=\"_blank\"><img src=\"/assets/images/logos/naver.png\" alt=\"NAVER\"></a>\r\n			</p>\r\n			<p>\r\n				<a href=\"https://search.shopping.naver.com/ns/search?query="
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\" target=\"_blank\"><img src=\"/assets/images/logos/naverplus.png\" alt=\"Naver 플러스스토어\"></a>\r\n			</p>\r\n		</dd>\r\n		<dt>SNS검색</dt>\r\n		<dd>\r\n			<p><a href=\"https://www.instagram.com/explore/search/keyword/?q="
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\" target=\"_blank\"><img src=\"/assets/images/logos/instagram.png\" alt=\"Instagram\"></a></p>\r\n			<p><a href=\"https://www.youtube.com/results?search_query="
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\" target=\"_blank\"><img src=\"/assets/images/logos/youtube.png\" alt=\"Youtube\"></a></p>\r\n		</dd>\r\n	</dl>\r\n</header>\r\n<!-- //Header -->\r\n\r\n<!-- 키워드 분석 (요약) -->\r\n<section class=\"analysis\">\r\n	<header>\r\n		<h4 class=\"title keyword\">키워드 분석 <span>(요약)</span></h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca817eb4edc749cc388846#2563a1f718ca81ce9797e711246811e5')\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width:345px;\">\r\n						키워드에 대한 주요 정보를 한 눈에 볼 수 있습니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div> \r\n		</div>\r\n	</header>\r\n	<ul class=\"analysisContent\">\r\n		<li class=\"type1\">\r\n			<span class=\"title blog\">블로그 글 수</span>\r\n			<p><em>"
    + alias2((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias4).call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordCount") : depth0)) != null ? lookupProperty(stack1,"blogCount") : stack1),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":62,"column":10},"end":{"line":62,"column":53}}}))
    + "</em>개</p>\r\n			<a href=\"https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query="
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\" target=\"_blank\"><span>바로가기</span></a>\r\n		</li>\r\n		<li class=\"type1\">\r\n			<span class=\"title cafe\">카페 글 수</span>\r\n			<p><em>"
    + alias2((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias4).call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordCount") : depth0)) != null ? lookupProperty(stack1,"cafeCount") : stack1),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":67,"column":10},"end":{"line":67,"column":53}}}))
    + "</em>개</p>\r\n			<a href=\"https://search.naver.com/search.naver?ssc=tab.cafe.all&sm=tab_jum&query="
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\" target=\"_blank\"><span>바로가기</span></a>\r\n		</li>\r\n		<li class=\"type1\">\r\n			<span class=\"title kin\">지식인 글 수</span>\r\n			<p><em>"
    + alias2((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias4).call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordCount") : depth0)) != null ? lookupProperty(stack1,"kinCount") : stack1),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":72,"column":10},"end":{"line":72,"column":52}}}))
    + "</em>개</p>\r\n			<a href=\"https://search.naver.com/search.naver?ssc=tab.kin.kqna&where=kin&sm=tab_jum&query="
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\" target=\"_blank\"><span>바로가기</span></a>\r\n		</li>\r\n		<li class=\"type1\">\r\n			<span class=\"title web\">웹문서 수</span>\r\n			<p><em>"
    + alias2((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias4).call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordCount") : depth0)) != null ? lookupProperty(stack1,"webCount") : stack1),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":77,"column":10},"end":{"line":77,"column":52}}}))
    + "</em>개</p>\r\n			<a href=\"https://search.naver.com/search.naver?ssc=tab.nx.all&where=nexearch&sm=tab_jum&query="
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\" target=\"_blank\"><span>바로가기</span></a>\r\n		</li>\r\n		<li class=\"type1\">\r\n			<span class=\"title\">쇼핑 상품수</span>\r\n			<p><em>"
    + alias2((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias4).call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"shoppingCount") : stack1),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":82,"column":10},"end":{"line":82,"column":53}}}))
    + "</em>개</p>\r\n		</li>\r\n		<li class=\"type1\">\r\n			<span class=\"title\">조회수(PC+모바일)</span>\r\n			<p><em>"
    + alias2((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias4).call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"sumCount") : stack1),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":86,"column":10},"end":{"line":86,"column":48}}}))
    + "</em>개</p>\r\n		</li>\r\n		<li class=\"type1\">\r\n			<span class=\"title\">경쟁강도</span>\r\n			\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias4).call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"baseInfo") : depth0)) != null ? lookupProperty(stack1,"rate") : stack1),">",100,{"name":"ifCond","hash":{},"fn":container.program(7, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":91,"column":3},"end":{"line":111,"column":14}}})) != null ? stack1 : "")
    + "		</li>\r\n		<li class=\"type1\">\r\n			<span class=\"title\">광고효율</span>\r\n			<p class=\"positive\">\r\n				<span>\r\n					<a href=\"/estimate/"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"param") : depth0)) != null ? lookupProperty(stack1,"keyword") : stack1), depth0))
    + "\" target=\"_blank\">보기</a>\r\n				</span>\r\n			</p>\r\n		</li>\r\n	</ul>\r\n</section>\r\n<!-- //키워드 분석 (요약) -->\r\n\r\n<!-- 쇼핑성 -->\r\n<section class=\"analysis\">   \r\n	<header>\r\n		<h4 class=\"title shopping\">쇼핑성</h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca817eb4edc749cc388846#2563a1f718ca81a89500de23896f7601');\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 415px;\">\r\n						해당 키워드가 정보 검색용인지 구매 의도 중심인지 판단할 수 있습니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>\r\n		</div>\r\n	</header>\r\n\r\n	<!-- Tab -->\r\n	<div class=\"tabType1\">\r\n		<button type=\"button\" class=\"selected\" onclick=\"$(this).addClass('selected').siblings().removeClass('selected').parent('.tabType1').siblings('.pc').show().siblings('section').hide();\">PC</button>\r\n		<button type=\"button\" onclick=\"$(this).addClass('selected').siblings().removeClass('selected').parent('.tabType1').siblings('.mobile').show().siblings('section').hide();\">모바일</button>\r\n	</div>\r\n	<!-- //Tab -->\r\n\r\n	<!-- PC -->\r\n	<section class=\"pc\">\r\n		<h5 class=\"hidden\">PC</h5>\r\n		<ul class=\"analysisContent\">\r\n			<li class=\"type3\">\r\n				<strong>검색 탭</strong>\r\n				<div class=\"items\">\r\n					<strong><em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordSection") : depth0)) != null ? lookupProperty(stack1,"pcranking") : stack1), depth0))
    + "</em>번째</strong>					\r\n				</div>\r\n			</li>\r\n			<li class=\"type3\">\r\n				<div class=\"items\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordSection") : depth0)) != null ? lookupProperty(stack1,"pclist") : stack1),{"name":"each","hash":{},"fn":container.program(20, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":159,"column":5},"end":{"line":165,"column":14}}})) != null ? stack1 : "")
    + "				</div>\r\n			</li>\r\n			\r\n			<li class=\"type3\">\r\n				<strong>검색 섹션</strong>\r\n				<div class=\"items\">\r\n					<strong><em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordSection") : depth0)) != null ? lookupProperty(stack1,"pcranking2") : stack1), depth0))
    + "</em>번째</strong>					\r\n				</div>\r\n			</li>\r\n			<li class=\"type3\">\r\n				<div class=\"items\">					\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordSection") : depth0)) != null ? lookupProperty(stack1,"pclist2") : stack1),{"name":"each","hash":{},"fn":container.program(25, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":177,"column":5},"end":{"line":187,"column":14}}})) != null ? stack1 : "")
    + "				</div>\r\n			</li>\r\n		</ul>\r\n	</section>\r\n	<!-- //PC -->\r\n\r\n	<!-- 모바일 -->\r\n	<section class=\"mobile\" style=\"display: none;\">\r\n		<h5 class=\"hidden\">모바일</h5>\r\n		<ul class=\"analysisContent\">\r\n			<li class=\"type3\">\r\n				<strong>검색 탭</strong>\r\n				<div class=\"items\">\r\n					<strong><em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordSection") : depth0)) != null ? lookupProperty(stack1,"mobileranking") : stack1), depth0))
    + "</em>번째</strong>\r\n				</div>\r\n			</li>\r\n			<li class=\"type3\">			\r\n				<div class=\"items\">			\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordSection") : depth0)) != null ? lookupProperty(stack1,"mobilelist") : stack1),{"name":"each","hash":{},"fn":container.program(20, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":206,"column":5},"end":{"line":212,"column":14}}})) != null ? stack1 : "")
    + "				</div>\r\n			</li>\r\n			\r\n			<li class=\"type3\">\r\n				<strong>검색 섹션</strong>\r\n				<div class=\"items\">\r\n					<strong><em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordSection") : depth0)) != null ? lookupProperty(stack1,"mobileranking2") : stack1), depth0))
    + "</em>번째</strong>\r\n				</div>\r\n			</li>\r\n			<li class=\"type3\">\r\n				<div class=\"items\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias3,((stack1 = (depth0 != null ? lookupProperty(depth0,"keywordSection") : depth0)) != null ? lookupProperty(stack1,"mobilelist2") : stack1),{"name":"each","hash":{},"fn":container.program(25, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":224,"column":5},"end":{"line":234,"column":14}}})) != null ? stack1 : "")
    + "				</div>\r\n			</li>\r\n		</ul>\r\n	</section>\r\n	<!-- //모바일 -->\r\n	\r\n</section>\r\n<!-- //쇼핑성 -->\r\n\r\n";
},"useData":true});
templates['keyword_category'] = template({"1":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"categories1") : depth0),{"name":"each","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":32,"column":6},"end":{"line":37,"column":15}}})) != null ? stack1 : "");
},"2":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "							<p class=\"flow\">\r\n								<b>"
    + alias3(((helper = (helper = lookupProperty(helpers,"name") || (depth0 != null ? lookupProperty(depth0,"name") : depth0)) != null ? helper : alias2),(typeof helper === "function" ? helper.call(alias1,{"name":"name","hash":{},"data":data,"loc":{"start":{"line":34,"column":11},"end":{"line":34,"column":19}}}) : helper)))
    + "</b>\r\n								<span>"
    + alias3((lookupProperty(helpers,"toPercent")||(depth0 && lookupProperty(depth0,"toPercent"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"score") : depth0),{"name":"toPercent","hash":{},"data":data,"loc":{"start":{"line":35,"column":14},"end":{"line":35,"column":33}}}))
    + "%</span>\r\n							</p>\r\n";
},"4":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"categories2") : depth0),{"name":"each","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":43,"column":6},"end":{"line":48,"column":15}}})) != null ? stack1 : "");
},"6":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"categories3") : depth0),{"name":"each","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":54,"column":6},"end":{"line":59,"column":15}}})) != null ? stack1 : "");
},"8":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"categories4") : depth0),{"name":"each","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":65,"column":6},"end":{"line":70,"column":15}}})) != null ? stack1 : "");
},"10":function(container,depth0,helpers,partials,data) {
    return "			<li>"
    + container.escapeExpression(container.lambda(depth0, depth0))
    + "</li>\r\n";
},"12":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "			<li>"
    + alias4(((helper = (helper = lookupProperty(helpers,"nluKeyword") || (depth0 != null ? lookupProperty(depth0,"nluKeyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"nluKeyword","hash":{},"data":data,"loc":{"start":{"line":117,"column":7},"end":{"line":117,"column":21}}}) : helper)))
    + "("
    + alias4(((helper = (helper = lookupProperty(helpers,"nluType") || (depth0 != null ? lookupProperty(depth0,"nluType") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"nluType","hash":{},"data":data,"loc":{"start":{"line":117,"column":22},"end":{"line":117,"column":33}}}) : helper)))
    + ")</li>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<section class=\"analysisDetail\">\r\n	<header style=\"justify-content: flex-start;\">\r\n		<h4 class=\"title\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"query") || (depth0 != null ? lookupProperty(depth0,"query") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"query","hash":{},"data":data,"loc":{"start":{"line":3,"column":20},"end":{"line":3,"column":29}}}) : helper)))
    + "("
    + alias4(((helper = (helper = lookupProperty(helpers,"strQueryType") || (depth0 != null ? lookupProperty(depth0,"strQueryType") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"strQueryType","hash":{},"data":data,"loc":{"start":{"line":3,"column":30},"end":{"line":3,"column":46}}}) : helper)))
    + " 키워드)</h4>\r\n		 \r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca81669122c1f44964f57b');\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 450px;\">\r\n						키워드가 네이버에서 어떤 카테고리로 인식되는지 비율로 확인할 수 있습니다.\r\n						<a style=\"position: absolute;right: 20px;bottom: 16px;font-weight: 500;font-size: 12px;color: #307EF7;\" href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>   \r\n		</div>\r\n	</header>\r\n	  \r\n	<table class=\"tableOverview\">\r\n		<colgroup>\r\n			<col width=\"197\">\r\n		</colgroup>\r\n		<thead>\r\n			<tr>\r\n				<th scope=\"col\">카테고리1</th>\r\n				<th scope=\"col\">카테고리2</th>\r\n				<th scope=\"col\">카테고리3</th>\r\n				<th scope=\"col\">카테고리4</th>\r\n			</tr>\r\n		</thead>\r\n		<tbody>\r\n			<tr>\r\n				<td>\r\n"
    + ((stack1 = lookupProperty(helpers,"if").call(alias1,(depth0 != null ? lookupProperty(depth0,"isCategory1") : depth0),{"name":"if","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":31,"column":5},"end":{"line":38,"column":12}}})) != null ? stack1 : "")
    + "				</td>\r\n				\r\n				<td>\r\n"
    + ((stack1 = lookupProperty(helpers,"if").call(alias1,(depth0 != null ? lookupProperty(depth0,"isCategory2") : depth0),{"name":"if","hash":{},"fn":container.program(4, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":42,"column":5},"end":{"line":49,"column":12}}})) != null ? stack1 : "")
    + "				</td>\r\n				\r\n				<td>\r\n"
    + ((stack1 = lookupProperty(helpers,"if").call(alias1,(depth0 != null ? lookupProperty(depth0,"isCategory3") : depth0),{"name":"if","hash":{},"fn":container.program(6, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":53,"column":5},"end":{"line":60,"column":12}}})) != null ? stack1 : "")
    + "				</td>\r\n				\r\n				<td>\r\n"
    + ((stack1 = lookupProperty(helpers,"if").call(alias1,(depth0 != null ? lookupProperty(depth0,"isCategory4") : depth0),{"name":"if","hash":{},"fn":container.program(8, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":64,"column":5},"end":{"line":71,"column":12}}})) != null ? stack1 : "")
    + "				</td>\r\n				\r\n			</tr>\r\n			\r\n			\r\n		</tbody>\r\n	</table>\r\n</section>\r\n\r\n<section class=\"analysis case\">\r\n	<header>\r\n		<h4 class=\"title\">텀즈</h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca81669122c1f44964f57b');\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 350px;\">\r\n						상품명에서 네이버가 인식한 핵심 단어 단위를 표시합니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>\r\n		</div>\r\n	</header>\r\n	<ul class=\"tags\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"termsList") : depth0),{"name":"each","hash":{},"fn":container.program(10, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":95,"column":2},"end":{"line":97,"column":11}}})) != null ? stack1 : "")
    + "	</ul>\r\n</section>\r\n\r\n\r\n<section class=\"analysis case\">\r\n	<header>\r\n		<h4 class=\"title\">nlu 텀즈</h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca81669122c1f44964f57b');\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 370px;\">\r\n						네이버의 의미 분석(NLU)으로 해석된 문맥 단위 키워드입니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>\r\n		</div>\r\n	</header>\r\n	<ul class=\"tags\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"nluTerms") : depth0),{"name":"each","hash":{},"fn":container.program(12, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":116,"column":2},"end":{"line":118,"column":11}}})) != null ? stack1 : "")
    + "	</ul>\r\n</section>";
},"useData":true});
templates['keyword_chart'] = template({"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=container.lambda, alias2=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<!-- 트렌드 (검색트렌드, 쇼핑클릭트렌드) -->\r\n<section class=\"analysis\">\r\n	<header>\r\n		<h4 class=\"title trend\">트렌드 <span>(검색트렌드, 쇼핑클릭트렌드)</span></h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca817eb4edc749cc388846#2563a1f718ca8115b9f4cb54fd770be6')\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 430px;\">\r\n						키워드의 검색·클릭 추이를 통해 시즌성과 성장 흐름을 확인할 수 있습니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>\r\n		</div>   \r\n	</header>\r\n	<ul class=\"analysisContent\">\r\n		<!-- 일자 -->\r\n		<li class=\"type3\">\r\n			<strong>일자</strong>\r\n			<div class=\"select normal\" data-selected=\"1\">\r\n				<button type=\"button\"></button>\r\n				<ul>\r\n					<li><button type=\"button\" id=\"timeUnitDate\" data-value=\"date\">일간</button></li>\r\n					<li><button type=\"button\" id=\"timeUnitWeek\" data-value=\"week\">주간</button></li>\r\n					<li><button type=\"button\" id=\"timeUnitMonth\" data-value=\"month\">월간</button></li>\r\n				</ul>\r\n			</div>\r\n			<div class=\"dateRange\">\r\n				<input type=\"text\" class=\"textfield\" id=\"from\">\r\n				-\r\n				<input type=\"text\" class=\"textfield\" id=\"to\">\r\n			</div>\r\n		</li>\r\n		<!-- //일자 -->\r\n\r\n		<!-- 기기별 -->\r\n		<li class=\"type3\" style=\"width: 430px;\">\r\n			<strong>기기별</strong>\r\n			<label class=\"radio\"><input type=\"radio\" name=\"dev\"  value=\"\" checked>전체</label>\r\n			<label class=\"radio\"><input type=\"radio\" name=\"dev\" value=\"pc\">PC</label>\r\n			<label class=\"radio\"><input type=\"radio\" name=\"dev\" value=\"mo\">모바일</label>\r\n		</li>\r\n		<!-- //기기별 -->\r\n\r\n		<!-- 성별 -->\r\n		<li class=\"type3\" style=\"width: calc(100% - 430px);\">\r\n			<strong>성별</strong>\r\n			<label class=\"radio\"><input type=\"radio\" name=\"gen\" value=\"\" checked>전체</label>\r\n			<label class=\"radio\"><input type=\"radio\" name=\"gen\" value=\"m\">남자</label>\r\n			<label class=\"radio\"><input type=\"radio\" name=\"gen\" value=\"f\">여자</label>\r\n		</li>\r\n		<!-- //성별 -->\r\n\r\n		<!-- 연령 -->\r\n		<li class=\"type3\">\r\n			<strong>연령별</strong>\r\n			<label class=\"radio\"><input type=\"checkbox\" name=\"ag\" value=\"\" checked>전체</label>\r\n			<label class=\"radio\"><input type=\"checkbox\" name=\"ag\" value=\"10\">10대</label>\r\n			<label class=\"radio\"><input type=\"checkbox\" name=\"ag\" value=\"20\">20대</label>\r\n			<label class=\"radio\"><input type=\"checkbox\" name=\"ag\" value=\"30\">30대</label>\r\n			<label class=\"radio\"><input type=\"checkbox\" name=\"ag\" value=\"40\">40대</label>\r\n			<label class=\"radio\"><input type=\"checkbox\" name=\"ag\" value=\"50\">50대</label>\r\n			<label class=\"radio\"><input type=\"checkbox\" name=\"ag\" value=\"60\">60대 이상</label>\r\n		</li>\r\n		<!-- //연령 -->\r\n\r\n		<!-- Graphs -->\r\n		<li class=\"graphs\">\r\n			<!-- 기간별 트렌드 추세 -->\r\n			<section class=\"full\">\r\n				<h5 class=\"title\">기간별 트렌드 추세</h5>\r\n				<div class=\"graph\">\r\n					<canvas id=\"trendChart\" width=\"700\" height=\"300\"></canvas>\r\n				</div>\r\n			</section>\r\n			<!-- //기간별 트렌드 추세 -->\r\n\r\n			<!-- 기기별 검색율 -->\r\n			<section>\r\n				<h5 class=\"title\">기기별 검색율</h5>\r\n				<div class=\"graph\">\r\n					<p class=\"donutChartType1\"><span>그래프</span></p>\r\n					<dl>\r\n						<dt>PC</dt><dd>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"deviceTrend") : depth0)) != null ? lookupProperty(stack1,"pc") : stack1), depth0))
    + "</dd>\r\n						<dt>모바일</dt><dd>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"deviceTrend") : depth0)) != null ? lookupProperty(stack1,"mo") : stack1), depth0))
    + "</dd>\r\n					</dl>\r\n				</div>\r\n			</section>\r\n			<!-- //기기별 검색율 -->\r\n\r\n			<!-- 성별 검색율 -->\r\n			<section>\r\n				<h5 class=\"title\">성별 검색율</h5>\r\n				<div class=\"graph\">\r\n					<p class=\"donutChartType1\"><span>그래프</span></p>\r\n					<dl>\r\n						<dt>남성</dt><dd>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"genderTrend") : depth0)) != null ? lookupProperty(stack1,"m") : stack1), depth0))
    + "</dd>\r\n						<dt>여성</dt><dd>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"genderTrend") : depth0)) != null ? lookupProperty(stack1,"f") : stack1), depth0))
    + "</dd>\r\n					</dl>\r\n				</div>\r\n			</section>\r\n			<!-- //성별 검색율 -->\r\n\r\n			<!-- 연령별 클릭율 -->\r\n			<section>\r\n				<h5 class=\"title\">연령별 클릭율</h5>\r\n				<div class=\"graph\">\r\n					<ul class=\"barChartType1\">\r\n						<ul class=\"barChartType1\">\r\n							<li>\r\n								<span>10대</span>\r\n								<div>\r\n									<strong>10대</strong>\r\n									클릭율 <em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"ageTrend") : depth0)) != null ? lookupProperty(stack1,"r10") : stack1), depth0))
    + "</em>\r\n								</div>\r\n							</li>\r\n							<li>\r\n								<span>20대</span>\r\n								<div>\r\n									<strong>20대</strong>\r\n									클릭율 <em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"ageTrend") : depth0)) != null ? lookupProperty(stack1,"r20") : stack1), depth0))
    + "</em>\r\n								</div>\r\n							</li>\r\n							<li>\r\n								<span>30대</span>\r\n								<div>\r\n									<strong>30대</strong>\r\n									클릭율 <em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"ageTrend") : depth0)) != null ? lookupProperty(stack1,"r30") : stack1), depth0))
    + "</em>\r\n								</div>\r\n							</li>\r\n							<li>\r\n								<span>40대</span>\r\n								<div>\r\n									<strong>40대</strong>\r\n									클릭율 <em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"ageTrend") : depth0)) != null ? lookupProperty(stack1,"r40") : stack1), depth0))
    + "</em>\r\n								</div>\r\n							</li>\r\n							<li>\r\n								<span>50대</span>\r\n								<div>\r\n									<strong>50대</strong>\r\n									클릭율 <em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"ageTrend") : depth0)) != null ? lookupProperty(stack1,"r50") : stack1), depth0))
    + "</em>\r\n								</div>\r\n							</li>\r\n							<li>\r\n								<span>60대</span>\r\n								<div>\r\n									<strong>60대</strong>\r\n									클릭율 <em>"
    + alias2(alias1(((stack1 = (depth0 != null ? lookupProperty(depth0,"ageTrend") : depth0)) != null ? lookupProperty(stack1,"r60") : stack1), depth0))
    + "</em>\r\n								</div>\r\n							</li>\r\n						</ul>\r\n\r\n					</ul>\r\n				</div>\r\n			</section>\r\n			<!-- //연령별 클릭율 -->\r\n		</li>\r\n		<!-- //Graphs -->\r\n	</ul>\r\n</section>\r\n<!-- //트렌드 (검색트렌드, 쇼핑클릭트렌드) -->";
},"useData":true});
templates['keyword_coupang_more_category'] = template({"1":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "		<p class=\"btnChangeCategory\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"DisplayItemCategoryCode") || (depth0 != null ? lookupProperty(depth0,"DisplayItemCategoryCode") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"DisplayItemCategoryCode","hash":{},"data":data,"loc":{"start":{"line":3,"column":40},"end":{"line":3,"column":67}}}) : helper)))
    + "\">\r\n			"
    + alias4(((helper = (helper = lookupProperty(helpers,"CategoryPath") || (depth0 != null ? lookupProperty(depth0,"CategoryPath") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"CategoryPath","hash":{},"data":data,"loc":{"start":{"line":4,"column":3},"end":{"line":4,"column":19}}}) : helper)))
    + "\r\n		</p>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<li class=\"\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"list") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":2,"column":1},"end":{"line":6,"column":10}}})) != null ? stack1 : "")
    + "</li>\r\n";
},"useData":true});
templates['keyword_coupang_top10'] = template({"1":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "			<tr>\r\n				<td class=\"subject\">"
    + alias3(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === "function" ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":24,"column":24},"end":{"line":24,"column":35}}}) : helper)))
    + "</td>\r\n				<td class=\"center\">"
    + alias3((lookupProperty(helpers,"qcSummary")||(depth0 && lookupProperty(depth0,"qcSummary"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"qc") : depth0),{"name":"qcSummary","hash":{},"data":data,"loc":{"start":{"line":25,"column":23},"end":{"line":25,"column":39}}}))
    + "</td>\r\n				<td class=\"center\">"
    + alias3((lookupProperty(helpers,"pvSummary")||(depth0 && lookupProperty(depth0,"pvSummary"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"pv") : depth0),{"name":"pvSummary","hash":{},"data":data,"loc":{"start":{"line":26,"column":23},"end":{"line":26,"column":39}}}))
    + "</td>\r\n				<td class=\"center\">"
    + alias3((lookupProperty(helpers,"toFixed1")||(depth0 && lookupProperty(depth0,"toFixed1"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"ctr") : depth0),{"name":"toFixed1","hash":{},"data":data,"loc":{"start":{"line":27,"column":23},"end":{"line":27,"column":39}}}))
    + "%</td>\r\n				<td class=\"center\">"
    + alias3((lookupProperty(helpers,"toFixed1")||(depth0 && lookupProperty(depth0,"toFixed1"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"impressionRate") : depth0),{"name":"toFixed1","hash":{},"data":data,"loc":{"start":{"line":28,"column":23},"end":{"line":28,"column":50}}}))
    + "%</td>\r\n				<td class=\"center\">"
    + alias3((lookupProperty(helpers,"toFixed1")||(depth0 && lookupProperty(depth0,"toFixed1"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"adImpressionWeight") : depth0),{"name":"toFixed1","hash":{},"data":data,"loc":{"start":{"line":29,"column":23},"end":{"line":29,"column":54}}}))
    + "%</td>\r\n				\r\n			</tr>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<table>\r\n	<colgroup>\r\n		<col class=\"static\" width=\"260\">\r\n		<col class=\"static\">\r\n		<col class=\"static\">\r\n		<col class=\"static\" width=\"120\">\r\n		<col class=\"static\">\r\n		<col class=\"static\" width=\"120\">\r\n	</colgroup>\r\n	<thead>\r\n	<tr>\r\n		<th scope=\"col\" class=\"subject\">키워드</th>\r\n		<th scope=\"col\" class=\"center\">조회수</th>\r\n		<th scope=\"col\" class=\"center\">클릭수</th>\r\n		<th scope=\"col\" class=\"center\">클릭율</th>\r\n		<th scope=\"col\" class=\"center\">노출증가</th>\r\n		<th scope=\"col\" class=\"center\">광고비중</th>\r\n		\r\n	</tr>\r\n	</thead>\r\n	<tbody>\r\n"
    + ((stack1 = (lookupProperty(helpers,"eachLimit")||(depth0 && lookupProperty(depth0,"eachLimit"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"Data") : depth0),5,{"name":"eachLimit","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":22,"column":2},"end":{"line":32,"column":16}}})) != null ? stack1 : "")
    + "	</tbody>\r\n</table>";
},"useData":true});
templates['keyword_related'] = template({"1":function(container,depth0,helpers,partials,data) {
    return "			<li>"
    + container.escapeExpression(container.lambda(depth0, depth0))
    + "</li>\r\n";
},"3":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "					<tr>\r\n						<th scope=\"row\" class=\"subject\"><a href=\"/keyword/"
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":198,"column":56},"end":{"line":198,"column":67}}}) : helper)))
    + "\" target=\"_blank\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":198,"column":85},"end":{"line":198,"column":96}}}) : helper)))
    + "</a></th>\r\n						<td scope=\"row\" class=\"subject\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"category") || (depth0 != null ? lookupProperty(depth0,"category") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"category","hash":{},"data":data,"loc":{"start":{"line":199,"column":38},"end":{"line":199,"column":50}}}) : helper)))
    + "</td>\r\n						<!--\r\n						<th scope=\"row\" class=\"sources\">\r\n							<button type=\"button\">3</button>\r\n							<ul class=\"hidden\">\r\n								<li>쇼핑연관검색어</li>\r\n								<li>쿠팡 자동완성 검색어</li>\r\n								<li>티몬 연관검색</li>\r\n							</ul>\r\n						</th>\r\n						-->\r\n						<td>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"p_click_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":210,"column":10},"end":{"line":210,"column":44}}}))
    + "</td>\r\n						<td>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"m_click_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":211,"column":10},"end":{"line":211,"column":44}}}))
    + "</td>\r\n						<td>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"sum_click_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":212,"column":10},"end":{"line":212,"column":46}}}))
    + "</td>\r\n						<td>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"shopping_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":213,"column":10},"end":{"line":213,"column":45}}}))
    + "</td>\r\n						<td>"
    + alias4((lookupProperty(helpers,"toFixed")||(depth0 && lookupProperty(depth0,"toFixed"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rate") : depth0),{"name":"toFixed","hash":{},"data":data,"loc":{"start":{"line":214,"column":10},"end":{"line":214,"column":26}}}))
    + "</td>\r\n						<td>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"p_ave_ctr") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":215,"column":10},"end":{"line":215,"column":40}}}))
    + "</td>\r\n						<td>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"m_ave_ctr") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":216,"column":10},"end":{"line":216,"column":40}}}))
    + "</td>\r\n						<td>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"p_ave_clk_cnt") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":217,"column":10},"end":{"line":217,"column":44}}}))
    + "</td>\r\n						<td>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"m_ave_clk_cnt") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":218,"column":10},"end":{"line":218,"column":44}}}))
    + "</td>\r\n						<td>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"avg_depth") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":219,"column":10},"end":{"line":219,"column":40}}}))
    + "</td>\r\n					</tr>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<!-- 연관키워드 -->\r\n<h3 class=\"hidden\">연관 키워드</h3>\r\n\r\n<!-- 연관 태그 -->\r\n<section class=\"analysis case\">\r\n	<header>\r\n		<h4 class=\"title\">네이버 쇼핑 연관</h4>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithComma")||(depth0 && lookupProperty(depth0,"joinWithComma"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"relatedKeywords") : depth0),{"name":"joinWithComma","hash":{},"data":data,"loc":{"start":{"line":8,"column":58},"end":{"line":8,"column":91}}}))
    + "\">복사</button>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca816fba17ff9b171c894a')\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 345px;\">\r\n						네이버 쇼핑 연관 키워드로 (,)콤마로 구분하여 복사됩니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>\r\n		</div>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithNewline")||(depth0 && lookupProperty(depth0,"joinWithNewline"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"relatedKeywords") : depth0),{"name":"joinWithNewline","hash":{},"data":data,"loc":{"start":{"line":18,"column":58},"end":{"line":18,"column":93}}}))
    + "\">복사</button>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca816fba17ff9b171c894a')\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 355px;\">\r\n						네이버쇼핑 연관 키워드로 엔터적용되어 세로로 복사됩니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>\r\n		</div>\r\n	</header>\r\n	<ul class=\"tags\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"relatedKeywords") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":30,"column":2},"end":{"line":32,"column":11}}})) != null ? stack1 : "")
    + "	</ul>\r\n</section>\r\n<!-- //연관 태그 -->\r\n\r\n<!-- 연관 태그 -->\r\n<section class=\"analysis case\">\r\n	<header>\r\n		<h4 class=\"title\">쿠팡 연관</h4>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithComma")||(depth0 && lookupProperty(depth0,"joinWithComma"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"cpangKeyword") : depth0),{"name":"joinWithComma","hash":{},"data":data,"loc":{"start":{"line":41,"column":58},"end":{"line":41,"column":88}}}))
    + "\">복사</button>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithNewline")||(depth0 && lookupProperty(depth0,"joinWithNewline"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"cpangKeyword") : depth0),{"name":"joinWithNewline","hash":{},"data":data,"loc":{"start":{"line":42,"column":58},"end":{"line":42,"column":90}}}))
    + "\">복사</button>\r\n	</header>\r\n	<ul class=\"tags\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"cpangKeyword") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":45,"column":2},"end":{"line":47,"column":11}}})) != null ? stack1 : "")
    + "	</ul>\r\n</section>\r\n<!-- //연관 태그 -->\r\n\r\n<!-- 연관 태그 -->\r\n<section class=\"analysis case\">\r\n	<header>\r\n		<h4 class=\"title\">쿠팡 자동완성</h4>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithComma")||(depth0 && lookupProperty(depth0,"joinWithComma"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"cpangAutoKeyword") : depth0),{"name":"joinWithComma","hash":{},"data":data,"loc":{"start":{"line":56,"column":58},"end":{"line":56,"column":92}}}))
    + "\">복사</button>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithNewline")||(depth0 && lookupProperty(depth0,"joinWithNewline"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"cpangAutoKeyword") : depth0),{"name":"joinWithNewline","hash":{},"data":data,"loc":{"start":{"line":57,"column":58},"end":{"line":57,"column":94}}}))
    + "\">복사</button>\r\n	</header>\r\n	<ul class=\"tags\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"cpangAutoKeyword") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":60,"column":2},"end":{"line":62,"column":11}}})) != null ? stack1 : "")
    + "	</ul>\r\n</section>\r\n<!-- //연관 태그 -->\r\n\r\n\r\n\r\n<!-- 연관 태그 -->\r\n<section class=\"analysis case\">\r\n	<header>\r\n		<h4 class=\"title\">네이버 쇼핑  자동완성</h4>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithComma")||(depth0 && lookupProperty(depth0,"joinWithComma"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"autoKeywords") : depth0),{"name":"joinWithComma","hash":{},"data":data,"loc":{"start":{"line":73,"column":58},"end":{"line":73,"column":88}}}))
    + "\">복사</button>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithNewline")||(depth0 && lookupProperty(depth0,"joinWithNewline"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"autoKeywords") : depth0),{"name":"joinWithNewline","hash":{},"data":data,"loc":{"start":{"line":74,"column":58},"end":{"line":74,"column":90}}}))
    + "\">복사</button>\r\n	</header>\r\n	<ul class=\"tags\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"autoKeywords") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":77,"column":2},"end":{"line":79,"column":11}}})) != null ? stack1 : "")
    + "	</ul>\r\n</section>\r\n<!-- //연관 태그 -->\r\n\r\n<!-- 연관 태그 -->\r\n<section class=\"analysis case\">\r\n	<header>\r\n		<h4 class=\"title\">네이버 블로그</h4>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithComma")||(depth0 && lookupProperty(depth0,"joinWithComma"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"blogKeywords") : depth0),{"name":"joinWithComma","hash":{},"data":data,"loc":{"start":{"line":88,"column":58},"end":{"line":88,"column":88}}}))
    + "\">복사</button>\r\n		<button type=\"button\" class=\"aside btnCopy\" data-value=\""
    + alias3((lookupProperty(helpers,"joinWithNewline")||(depth0 && lookupProperty(depth0,"joinWithNewline"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"blogKeywords") : depth0),{"name":"joinWithNewline","hash":{},"data":data,"loc":{"start":{"line":89,"column":58},"end":{"line":89,"column":90}}}))
    + "\">복사</button>\r\n	</header>\r\n	<ul class=\"tags\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"blogKeywords") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":92,"column":2},"end":{"line":94,"column":11}}})) != null ? stack1 : "")
    + "	</ul>\r\n</section>  \r\n<!-- //연관 태그 -->\r\n\r\n \r\n<!-- 연관 검색어 -->\r\n<section class=\"filterGroup\" style=\"margin-top:50px;\">\r\n	<header>\r\n		<h4 class=\"title\">연관 검색어 <small>("
    + alias3((lookupProperty(helpers,"length")||(depth0 && lookupProperty(depth0,"length"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rKeyword") : depth0),{"name":"length","hash":{},"data":data,"loc":{"start":{"line":103,"column":35},"end":{"line":103,"column":54}}}))
    + "개)</small></h4>\r\n		<div class=\"tooltip\" onclick=\"window.open('https://rainy-cyclamen-990.notion.site/2563a1f718ca816fba17ff9b171c894a')\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>\r\n			<div style=\"left: -40px; width: 240px;\">\r\n						검색한 키워드의 연관키워드 입니다.\r\n						<a href=\"\">\r\n							[더 알아보기]\r\n						</a>  \r\n			</div>\r\n		</div>\r\n		<!-- <button type=\"button\" class=\"selectLike\" onclick=\"$(this).toggleClass('opened');$('.relatedFilters').toggle();\">출처</button> -->\r\n	</header>\r\n	<!--\r\n	<ul class=\"relatedFilters\" style=\"display: none;\">\r\n		<li>\r\n			<div><label class=\"check small\"><input type=\"checkbox\" class=\"checkAll\">네이버(100)</label></div>\r\n			<div class=\"targets\">\r\n				<label class=\"check2 small\"><input type=\"checkbox\">쇼핑연관검색어(20)</label>\r\n				<label class=\"check2 small\"><input type=\"checkbox\">네이버 통합 연관 검색어(30)</label>\r\n				<label class=\"check2 small\"><input type=\"checkbox\">네이버 자동완성 검색어(50)</label>\r\n			</div>\r\n		</li>\r\n		<li>\r\n			<div><label class=\"check small\"><input type=\"checkbox\" class=\"checkAll\">쿠팡(23)</label></div>\r\n			<div class=\"targets\">\r\n				<label class=\"check2 small\"><input type=\"checkbox\">쿠팡 자동완성 검색어(23)</label>\r\n			</div>\r\n		</li>\r\n		<li>\r\n			<div><label class=\"check small\"><input type=\"checkbox\" class=\"checkAll\">티몬(23)</label></div>\r\n			<div class=\"targets\">\r\n				<label class=\"check2 small\"><input type=\"checkbox\">티몬 연관검색어(12)</label>\r\n				<label class=\"check2 small\"><input type=\"checkbox\">티몬 자동검색어(11)</label>\r\n			</div>\r\n		</li>\r\n		<li>\r\n			<div><label class=\"check small\"><input type=\"checkbox\" class=\"checkAll\">카카오(23)</label></div>\r\n			<div class=\"targets\">\r\n				<label class=\"check2 small\"><input type=\"checkbox\">카카오 연관검색어(12)</label>\r\n				<label class=\"check2 small\"><input type=\"checkbox\">카카오 자동검색어(11)</label>\r\n			</div>\r\n		</li>\r\n		<li>\r\n			<div><label class=\"check small\"><input type=\"checkbox\" class=\"checkAll\">ㅁㅁ(23)</label></div>\r\n			<div class=\"targets\">\r\n				<label class=\"check2 small\"><input type=\"checkbox\">ㅁㅁ 연관검색어(12)</label>\r\n				<label class=\"check2 small\"><input type=\"checkbox\">ㅁㅁ 자동검색어(11)</label>\r\n			</div>\r\n		</li>\r\n	</ul>\r\n	-->\r\n</section>\r\n<!-- //연관 검색어 -->\r\n\r\n<!-- Grid -->\r\n<div class=\"gridContainer\">\r\n	<!--\r\n	<div class=\"utilities\">\r\n		<button type=\"button\" class=\"aside set\" onclick=\"popup('#setItem')\">항목 설정</button>\r\n		<div class=\"tooltip\">\r\n			<button type=\"button\"><span>도움말 보기</span></button>			\r\n		</div>\r\n	</div>\r\n	-->\r\n	<div class=\"buttons\">\r\n		<button type=\"button\" class=\"aside excel\" id=\"btnRelExcel\">엑셀 다운로드</button>\r\n		<!-- <button type=\"button\" class=\"aside expand\"><span>가로 확장</span></button> -->\r\n	</div>\r\n\r\n	<div class=\"grid\">\r\n		<table style=\"min-width: 1550px;\" id=\"relDataTable\">\r\n			<colgroup>\r\n				<col width=\"250\">\r\n				<col width=\"180\">\r\n			</colgroup>\r\n			<thead>\r\n				<tr>\r\n					<th scope=\"col\" class=\"subject\"><button type=\"button\">키워드</button></th>\r\n					<!--<th scope=\"col\">출처</th>-->\r\n					<th scope=\"col\" class=\"subject\"><button type=\"button\" class=\"sort\">카테고리</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">PC 조회수</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">모바일 조회수</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">합계</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">상품수</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">경쟁도</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">PC클릭률</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">모바일클릭률</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">PC클릭수</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">모바일클릭수</button></th>\r\n					<th scope=\"col\"><button type=\"button\" class=\"sort\">노출광고수</button></th>\r\n				</tr>\r\n			</thead>\r\n			<tbody>\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"rKeyword") : depth0),{"name":"each","hash":{},"fn":container.program(3, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":196,"column":4},"end":{"line":221,"column":13}}})) != null ? stack1 : "")
    + "			</tbody>\r\n		</table>\r\n	</div>\r\n</div>\r\n<!-- //Grid -->\r\n\r\n\r\n";
},"useData":true});
templates['rankGroup'] = template({"1":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "			<tr>\r\n				<td class=\"noline leftalign btnSelectGroup\" style=\"padding-left:30px;border-bottom:1px solid #f2f2f2;\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"group_id") || (depth0 != null ? lookupProperty(depth0,"group_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"group_id","hash":{},"data":data,"loc":{"start":{"line":19,"column":116},"end":{"line":19,"column":128}}}) : helper)))
    + "\">\r\n					"
    + alias4(((helper = (helper = lookupProperty(helpers,"group_name") || (depth0 != null ? lookupProperty(depth0,"group_name") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"group_name","hash":{},"data":data,"loc":{"start":{"line":20,"column":5},"end":{"line":20,"column":19}}}) : helper)))
    + "\r\n				</td>\r\n				\r\n				<td class=\"righttalign\" style=\"border-bottom:1px solid #f2f2f2;\">\r\n					<button class=\"secondaryXsmall btnDeleteGroup\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"group_id") || (depth0 != null ? lookupProperty(depth0,"group_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"group_id","hash":{},"data":data,"loc":{"start":{"line":24,"column":61},"end":{"line":24,"column":73}}}) : helper)))
    + "\" style=\"height:unset;padding:4px 8px;\">x</button>\r\n				</td>\r\n			</tr>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<table>\r\n	<colgroup>\r\n		<col width=\"*\">\r\n		<col width=\"60\">\r\n	</colgroup>\r\n	<thead>\r\n		<tr>	\r\n			<th class=\"centeralign\" colspan=\"2\">\r\n				<a type=\"button\" class=\"secondaryXSmall\" onclick=\"popup('#addGroup')\">그룹추가</a>\r\n			</th>\r\n			\r\n		</tr>\r\n	</thead>\r\n	<tbody>\r\n		<tr><td colspan=\"2\" class=\"centeralign btnSelectGroup\" data-id=\"-1\" style=\"border-bottom:1px solid #f2f2f2;\">전체</td></tr>\r\n		<tr><td colspan=\"2\" class=\"centeralign btnSelectGroup\" data-id=\"0\" style=\"border-bottom:1px solid #f2f2f2;\">그룹미지정</td></tr>\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"list") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":17,"column":2},"end":{"line":27,"column":11}}})) != null ? stack1 : "")
    + "	</tbody>\r\n</table>";
},"useData":true});
templates['rankList'] = template({"1":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank_type") : depth0),"==","S",{"name":"ifCond","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":2,"column":1},"end":{"line":83,"column":12}}})) != null ? stack1 : "")
    + "\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank_type") : depth0),"==","P",{"name":"ifCond","hash":{},"fn":container.program(27, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":85,"column":1},"end":{"line":166,"column":12}}})) != null ? stack1 : "")
    + "\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank_type") : depth0),"==","M",{"name":"ifCond","hash":{},"fn":container.program(30, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":168,"column":1},"end":{"line":247,"column":12}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank_type") : depth0),"==","L",{"name":"ifCond","hash":{},"fn":container.program(32, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":248,"column":1},"end":{"line":328,"column":12}}})) != null ? stack1 : "");
},"2":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "	<!-- item: 상점명 1 -->\r\n	<li class=\"typeShop\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":4,"column":31},"end":{"line":4,"column":42}}}) : helper)))
    + "\">\r\n		<a href=\"/rank/s/"
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":5,"column":19},"end":{"line":5,"column":30}}}) : helper)))
    + "\">\r\n			<div class=\"con\">\r\n				<p>\r\n					<em>상점명</em>\r\n					<span>최종 추적시간 "
    + alias4(((helper = (helper = lookupProperty(helpers,"last_date") || (depth0 != null ? lookupProperty(depth0,"last_date") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"last_date","hash":{},"data":data,"loc":{"start":{"line":9,"column":19},"end":{"line":9,"column":32}}}) : helper)))
    + "</span>\r\n				</p>\r\n\r\n				<strong>"
    + alias4((lookupProperty(helpers,"truncate")||(depth0 && lookupProperty(depth0,"truncate"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"title") : depth0),32,{"name":"truncate","hash":{},"data":data,"loc":{"start":{"line":12,"column":12},"end":{"line":12,"column":33}}}))
    + "</strong>\r\n				<dl class=\"type2\">\r\n					<dt>상품 수</dt><dd>"
    + alias4(((helper = (helper = lookupProperty(helpers,"found_count") || (depth0 != null ? lookupProperty(depth0,"found_count") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"found_count","hash":{},"data":data,"loc":{"start":{"line":14,"column":22},"end":{"line":14,"column":37}}}) : helper)))
    + "</dd>\r\n					<dt>키워드</dt><dd>"
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":15,"column":21},"end":{"line":15,"column":32}}}) : helper)))
    + "</dd>\r\n					<dt>몰이름</dt><dd>"
    + alias4(((helper = (helper = lookupProperty(helpers,"shop_name") || (depth0 != null ? lookupProperty(depth0,"shop_name") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"shop_name","hash":{},"data":data,"loc":{"start":{"line":16,"column":21},"end":{"line":16,"column":34}}}) : helper)))
    + "</dd>\r\n				</dl>\r\n				<div class=\"memoBox\">\r\n					<span>메모 :</span>\r\n				<input type=\"text\"class=\"memoInput\" name=\"memoInput\" value=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"memo") || (depth0 != null ? lookupProperty(depth0,"memo") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"memo","hash":{},"data":data,"loc":{"start":{"line":20,"column":64},"end":{"line":20,"column":72}}}) : helper)))
    + "\" placeholder=\"메모를 입력하세요...\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":20,"column":110},"end":{"line":20,"column":121}}}) : helper)))
    + "\" />\r\n			   <button type=\"button\" class=\"caseXmemo memoButton hidden\"  data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":21,"column":74},"end":{"line":21,"column":85}}}) : helper)))
    + "\"><span>수정</span></button>\r\n			   </div>\r\n			</div>\r\n\r\n			<div class=\"rank\">\r\n				<span>상품 내 최고 순위</span>\r\n				<div class=\"preview\">\r\n					<button type=\"button\"><span>미리보기</span></button>\r\n					<div>\r\n						<strong>"
    + alias4(((helper = (helper = lookupProperty(helpers,"title") || (depth0 != null ? lookupProperty(depth0,"title") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"title","hash":{},"data":data,"loc":{"start":{"line":30,"column":14},"end":{"line":30,"column":23}}}) : helper)))
    + "</strong>\r\n						<p>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(3, data, 0),"inverse":container.program(5, data, 0),"data":data,"loc":{"start":{"line":32,"column":7},"end":{"line":36,"column":18}}})) != null ? stack1 : "")
    + "						</p>\r\n						<dl class=\"type2\">\r\n							<dt>구매수</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"purchase_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(7, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":39,"column":23},"end":{"line":39,"column":110}}})) != null ? stack1 : "")
    + "</dd>\r\n							<dt>리뷰</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"review_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(11, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":40,"column":22},"end":{"line":40,"column":105}}})) != null ? stack1 : "")
    + "</dd>\r\n							<dt>찜</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"keep_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(13, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":41,"column":21},"end":{"line":41,"column":100}}})) != null ? stack1 : "")
    + "</dd>\r\n						</dl>\r\n\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(15, data, 0),"inverse":container.program(17, data, 0),"data":data,"loc":{"start":{"line":44,"column":6},"end":{"line":48,"column":17}}})) != null ? stack1 : "")
    + "					</div>\r\n				</div>\r\n\r\n				<p>\r\n					<strong>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(19, data, 0),"inverse":container.program(21, data, 0),"data":data,"loc":{"start":{"line":54,"column":6},"end":{"line":58,"column":17}}})) != null ? stack1 : "")
    + "					</strong>\r\n				</p>				\r\n			</div>\r\n\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(23, data, 0),"inverse":container.program(25, data, 0),"data":data,"loc":{"start":{"line":63,"column":3},"end":{"line":67,"column":14}}})) != null ? stack1 : "")
    + "		</a>\r\n\r\n		<div class=\"utilities\">\r\n			<button type=\"button\" class=\"caseXsmall refresh btnRequestRankingShop\"\r\n				data-mall-name=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"shop_name") || (depth0 != null ? lookupProperty(depth0,"shop_name") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"shop_name","hash":{},"data":data,"loc":{"start":{"line":72,"column":20},"end":{"line":72,"column":33}}}) : helper)))
    + "\"\r\n				data-keyword=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":73,"column":18},"end":{"line":73,"column":29}}}) : helper)))
    + "\"\r\n				data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":74,"column":13},"end":{"line":74,"column":24}}}) : helper)))
    + "\"><span>갱신</span></button>\r\n\r\n			<button type=\"button\" class=\"more\" onclick=\"$(this).next('.functionLayer').toggleClass('showing')\"><span>더보기</span></button>\r\n			<div class=\"functionLayer\" style=\"right: -40px; top: 100px;\">\r\n				<a href=\"/rank/s/history/"
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":78,"column":29},"end":{"line":78,"column":40}}}) : helper)))
    + "\">전체 기록 보기</a>\r\n				<button type=\"button\" class=\"btnDelete\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":79,"column":53},"end":{"line":79,"column":64}}}) : helper)))
    + "\">삭제하기</button>\r\n			</div>\r\n		</div>\r\n	</li>\r\n";
},"3":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "								<b>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"rank") || (depth0 != null ? lookupProperty(depth0,"rank") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"rank","hash":{},"data":data,"loc":{"start":{"line":33,"column":11},"end":{"line":33,"column":19}}}) : helper)))
    + "</b>위\r\n";
},"5":function(container,depth0,helpers,partials,data) {
    return "								없음\r\n";
},"7":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return container.escapeExpression((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"purchase_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":39,"column":55},"end":{"line":39,"column":90}}}));
},"9":function(container,depth0,helpers,partials,data) {
    return "-";
},"11":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return container.escapeExpression((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"review_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":40,"column":52},"end":{"line":40,"column":85}}}));
},"13":function(container,depth0,helpers,partials,data) {
    var lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return container.escapeExpression((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"keep_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":41,"column":49},"end":{"line":41,"column":80}}}));
},"15":function(container,depth0,helpers,partials,data) {
    return "							<div class=\"thumb\" style=\"background-image: url('/assets/images/common/noImg.svg');\"><span>썸네일</span></div>\r\n";
},"17":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "							<div class=\"thumb\" style=\"background-image: url('"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"img") || (depth0 != null ? lookupProperty(depth0,"img") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"img","hash":{},"data":data,"loc":{"start":{"line":47,"column":56},"end":{"line":47,"column":63}}}) : helper)))
    + "');\"><span>썸네일</span></div>\r\n";
},"19":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "							<b>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"rank") || (depth0 != null ? lookupProperty(depth0,"rank") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"rank","hash":{},"data":data,"loc":{"start":{"line":55,"column":10},"end":{"line":55,"column":18}}}) : helper)))
    + "</b>위\r\n";
},"21":function(container,depth0,helpers,partials,data) {
    return "							없음\r\n";
},"23":function(container,depth0,helpers,partials,data) {
    return "				<div class=\"thumb\" style=\"background-image: url('/assets/images/common/noImg.svg');\"><span>썸네일</span></div>\r\n";
},"25":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<div class=\"thumb\" style=\"background-image: url('"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"img") || (depth0 != null ? lookupProperty(depth0,"img") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"img","hash":{},"data":data,"loc":{"start":{"line":66,"column":53},"end":{"line":66,"column":60}}}) : helper)))
    + "');\"><span>썸네일</span></div>\r\n";
},"27":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "	<!-- item: 상품주소 -->\r\n	<li class=\"typeUrl\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":87,"column":30},"end":{"line":87,"column":41}}}) : helper)))
    + "\">\r\n		<a href=\"/rank/"
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":88,"column":17},"end":{"line":88,"column":28}}}) : helper)))
    + "\">\r\n			<div class=\"con\">\r\n				<p>\r\n					<em>상품주소</em>\r\n					<span>최종 추적시간 "
    + alias4(((helper = (helper = lookupProperty(helpers,"last_date") || (depth0 != null ? lookupProperty(depth0,"last_date") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"last_date","hash":{},"data":data,"loc":{"start":{"line":92,"column":19},"end":{"line":92,"column":32}}}) : helper)))
    + "</span>\r\n				</p>\r\n\r\n				<strong>"
    + alias4((lookupProperty(helpers,"truncate")||(depth0 && lookupProperty(depth0,"truncate"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"title") : depth0),32,{"name":"truncate","hash":{},"data":data,"loc":{"start":{"line":95,"column":12},"end":{"line":95,"column":33}}}))
    + "</strong>\r\n				<dl class=\"type2\">\r\n					<dt>키워드</dt><dd>"
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":97,"column":21},"end":{"line":97,"column":32}}}) : helper)))
    + "</dd>\r\n				</dl>\r\n				<div class=\"memoBox\">\r\n					<span>메모 : </span>\r\n				<input type=\"text\"class=\"memoInput\" name=\"memoInput\" value=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"memo") || (depth0 != null ? lookupProperty(depth0,"memo") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"memo","hash":{},"data":data,"loc":{"start":{"line":101,"column":64},"end":{"line":101,"column":72}}}) : helper)))
    + "\" placeholder=\"메모를 입력하세요...\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":101,"column":110},"end":{"line":101,"column":121}}}) : helper)))
    + "\" />\r\n			   <button type=\"button\" class=\"caseXmemo memoButton hidden\"  data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":102,"column":74},"end":{"line":102,"column":85}}}) : helper)))
    + "\"><span>수정</span></button>\r\n			   </div>\r\n			</div>\r\n\r\n			<div class=\"rank\">\r\n				<span>현재 순위</span>\r\n				<div class=\"preview\">\r\n					<button type=\"button\"><span>미리보기</span></button>\r\n					<div>\r\n						<strong>"
    + alias4(((helper = (helper = lookupProperty(helpers,"title") || (depth0 != null ? lookupProperty(depth0,"title") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"title","hash":{},"data":data,"loc":{"start":{"line":111,"column":14},"end":{"line":111,"column":23}}}) : helper)))
    + "</strong>\r\n						<p>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(28, data, 0),"inverse":container.program(5, data, 0),"data":data,"loc":{"start":{"line":113,"column":7},"end":{"line":117,"column":18}}})) != null ? stack1 : "")
    + "						</p>\r\n						<dl class=\"type2\">\r\n							<dt>구매수</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"purchase_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(7, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":120,"column":23},"end":{"line":120,"column":110}}})) != null ? stack1 : "")
    + "</dd>\r\n							<dt>리뷰</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"review_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(11, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":121,"column":22},"end":{"line":121,"column":105}}})) != null ? stack1 : "")
    + "</dd>\r\n							<dt>찜</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"keep_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(13, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":122,"column":21},"end":{"line":122,"column":100}}})) != null ? stack1 : "")
    + "</dd>\r\n						</dl>\r\n\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(15, data, 0),"inverse":container.program(17, data, 0),"data":data,"loc":{"start":{"line":125,"column":6},"end":{"line":129,"column":17}}})) != null ? stack1 : "")
    + "					</div>\r\n				</div>\r\n\r\n				<p>\r\n					<strong>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(19, data, 0),"inverse":container.program(21, data, 0),"data":data,"loc":{"start":{"line":135,"column":6},"end":{"line":139,"column":17}}})) != null ? stack1 : "")
    + "					</strong>\r\n				</p>\r\n			</div>\r\n\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(23, data, 0),"inverse":container.program(25, data, 0),"data":data,"loc":{"start":{"line":144,"column":3},"end":{"line":148,"column":14}}})) != null ? stack1 : "")
    + "		</a>\r\n\r\n		<div class=\"utilities\">\r\n			<button type=\"button\" class=\"caseXsmall refresh btnRequestRankingProduct\"\r\n				data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":153,"column":13},"end":{"line":153,"column":24}}}) : helper)))
    + "\"\r\n				data-mid=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"mid") || (depth0 != null ? lookupProperty(depth0,"mid") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"mid","hash":{},"data":data,"loc":{"start":{"line":154,"column":14},"end":{"line":154,"column":21}}}) : helper)))
    + "\"\r\n				data-url=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"address") || (depth0 != null ? lookupProperty(depth0,"address") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"address","hash":{},"data":data,"loc":{"start":{"line":155,"column":14},"end":{"line":155,"column":25}}}) : helper)))
    + "\"\r\n				data-keyword=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":156,"column":18},"end":{"line":156,"column":29}}}) : helper)))
    + "\"\r\n				data-product=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"title") || (depth0 != null ? lookupProperty(depth0,"title") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"title","hash":{},"data":data,"loc":{"start":{"line":157,"column":18},"end":{"line":157,"column":27}}}) : helper)))
    + "\"\r\n				data-img=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"img") || (depth0 != null ? lookupProperty(depth0,"img") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"img","hash":{},"data":data,"loc":{"start":{"line":158,"column":14},"end":{"line":158,"column":21}}}) : helper)))
    + "\"><span>갱신</span></button>\r\n\r\n			<button type=\"button\" class=\"more\" onclick=\"$(this).next('.functionLayer').toggleClass('showing')\"><span>더보기</span></button>\r\n			<div class=\"functionLayer\" style=\"right: -40px; top: 100px;\">\r\n				<button type=\"button\" class=\"btnDelete\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":162,"column":53},"end":{"line":162,"column":64}}}) : helper)))
    + "\">삭제하기</button>\r\n			</div>\r\n		</div>\r\n	</li>\r\n";
},"28":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "								<b>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"rank") || (depth0 != null ? lookupProperty(depth0,"rank") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"rank","hash":{},"data":data,"loc":{"start":{"line":114,"column":11},"end":{"line":114,"column":19}}}) : helper)))
    + "</b>\r\n";
},"30":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "	<!-- item: MID -->\r\n	<li class=\"typeUrl\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":170,"column":30},"end":{"line":170,"column":41}}}) : helper)))
    + "\">\r\n		<a href=\"/rank/"
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":171,"column":17},"end":{"line":171,"column":28}}}) : helper)))
    + "\">\r\n			<div class=\"con\">\r\n				<p>\r\n					<em>MID</em>\r\n					<span>최종 추적시간 "
    + alias4(((helper = (helper = lookupProperty(helpers,"last_date") || (depth0 != null ? lookupProperty(depth0,"last_date") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"last_date","hash":{},"data":data,"loc":{"start":{"line":175,"column":19},"end":{"line":175,"column":32}}}) : helper)))
    + "</span>\r\n				</p>\r\n\r\n				<strong>"
    + alias4((lookupProperty(helpers,"truncate")||(depth0 && lookupProperty(depth0,"truncate"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"title") : depth0),32,{"name":"truncate","hash":{},"data":data,"loc":{"start":{"line":178,"column":12},"end":{"line":178,"column":33}}}))
    + "</strong>\r\n				<dl class=\"type2\">\r\n					<dt>키워드</dt><dd>"
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":180,"column":21},"end":{"line":180,"column":32}}}) : helper)))
    + "</dd>					\r\n				</dl>\r\n				<div class=\"memoBox\">\r\n					<span>메모 : </span>\r\n				<input type=\"text\"class=\"memoInput\" name=\"memoInput\" value=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"memo") || (depth0 != null ? lookupProperty(depth0,"memo") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"memo","hash":{},"data":data,"loc":{"start":{"line":184,"column":64},"end":{"line":184,"column":72}}}) : helper)))
    + "\" placeholder=\"메모를 입력하세요...\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":184,"column":110},"end":{"line":184,"column":121}}}) : helper)))
    + "\" />\r\n			   <button type=\"button\" class=\"caseXmemo memoButton hidden\"  data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":185,"column":74},"end":{"line":185,"column":85}}}) : helper)))
    + "\"><span>수정</span></button>\r\n			   </div>\r\n			</div>\r\n\r\n			<div class=\"rank\">\r\n				<span>현재 순위</span>\r\n				<div class=\"preview\">\r\n					<button type=\"button\"><span>미리보기</span></button>\r\n					<div>\r\n						<strong>"
    + alias4(((helper = (helper = lookupProperty(helpers,"title") || (depth0 != null ? lookupProperty(depth0,"title") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"title","hash":{},"data":data,"loc":{"start":{"line":194,"column":14},"end":{"line":194,"column":23}}}) : helper)))
    + "</strong>\r\n						<p>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(28, data, 0),"inverse":container.program(5, data, 0),"data":data,"loc":{"start":{"line":196,"column":7},"end":{"line":200,"column":18}}})) != null ? stack1 : "")
    + "						</p>\r\n						<dl class=\"type2\">\r\n							<dt>구매수</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"purchase_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(7, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":203,"column":23},"end":{"line":203,"column":110}}})) != null ? stack1 : "")
    + "</dd>\r\n							<dt>리뷰</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"review_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(11, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":204,"column":22},"end":{"line":204,"column":105}}})) != null ? stack1 : "")
    + "</dd>\r\n							<dt>찜</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"keep_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(13, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":205,"column":21},"end":{"line":205,"column":100}}})) != null ? stack1 : "")
    + "</dd>\r\n						</dl>\r\n\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(15, data, 0),"inverse":container.program(17, data, 0),"data":data,"loc":{"start":{"line":208,"column":6},"end":{"line":212,"column":17}}})) != null ? stack1 : "")
    + "					</div>\r\n				</div>\r\n\r\n				<p>\r\n					<strong>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(19, data, 0),"inverse":container.program(21, data, 0),"data":data,"loc":{"start":{"line":218,"column":6},"end":{"line":222,"column":17}}})) != null ? stack1 : "")
    + "					</strong>\r\n				</p>\r\n			</div>\r\n\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(23, data, 0),"inverse":container.program(25, data, 0),"data":data,"loc":{"start":{"line":227,"column":3},"end":{"line":231,"column":14}}})) != null ? stack1 : "")
    + "		</a>\r\n\r\n		<div class=\"utilities\">\r\n			<button type=\"button\" class=\"caseXsmall refresh btnRequestRankingMid\"\r\n				data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":236,"column":13},"end":{"line":236,"column":24}}}) : helper)))
    + "\"\r\n				data-mid=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"mid") || (depth0 != null ? lookupProperty(depth0,"mid") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"mid","hash":{},"data":data,"loc":{"start":{"line":237,"column":14},"end":{"line":237,"column":21}}}) : helper)))
    + "\"\r\n				data-keyword=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":238,"column":18},"end":{"line":238,"column":29}}}) : helper)))
    + "\"\r\n				data-url=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"address") || (depth0 != null ? lookupProperty(depth0,"address") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"address","hash":{},"data":data,"loc":{"start":{"line":239,"column":14},"end":{"line":239,"column":25}}}) : helper)))
    + "\"><span>갱신</span></button>\r\n\r\n			<button type=\"button\" class=\"more\" onclick=\"$(this).next('.functionLayer').toggleClass('showing')\"><span>더보기</span></button>\r\n			<div class=\"functionLayer\" style=\"right: -40px; top: 100px;\">\r\n				<button type=\"button\" class=\"btnDelete\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":243,"column":53},"end":{"line":243,"column":64}}}) : helper)))
    + "\">삭제하기</button>\r\n			</div>\r\n		</div>\r\n	</li>\r\n";
},"32":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "	<!-- item: 플레이스 -->\r\n	<li class=\"typeUrl\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":250,"column":30},"end":{"line":250,"column":41}}}) : helper)))
    + "\">\r\n		<a href=\"/rank/"
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":251,"column":17},"end":{"line":251,"column":28}}}) : helper)))
    + "\">\r\n			<div class=\"con\">\r\n				<p>\r\n					<em>플레이스</em>\r\n					<span>최종 추적시간 "
    + alias4(((helper = (helper = lookupProperty(helpers,"last_date") || (depth0 != null ? lookupProperty(depth0,"last_date") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"last_date","hash":{},"data":data,"loc":{"start":{"line":255,"column":19},"end":{"line":255,"column":32}}}) : helper)))
    + "</span>\r\n				</p>\r\n\r\n				<strong>"
    + alias4((lookupProperty(helpers,"truncate")||(depth0 && lookupProperty(depth0,"truncate"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"title") : depth0),32,{"name":"truncate","hash":{},"data":data,"loc":{"start":{"line":258,"column":12},"end":{"line":258,"column":33}}}))
    + "</strong>\r\n				<dl class=\"type2\">\r\n					<dt>키워드</dt><dd>"
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":260,"column":21},"end":{"line":260,"column":32}}}) : helper)))
    + "</dd>\r\n				</dl>\r\n				<div class=\"memoBox\">\r\n					<span>메모 : </span>\r\n				<input type=\"text\"class=\"memoInput\" name=\"memoInput\" value=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"memo") || (depth0 != null ? lookupProperty(depth0,"memo") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"memo","hash":{},"data":data,"loc":{"start":{"line":264,"column":64},"end":{"line":264,"column":72}}}) : helper)))
    + "\" placeholder=\"메모를 입력하세요...\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":264,"column":110},"end":{"line":264,"column":121}}}) : helper)))
    + "\" />\r\n			   <button type=\"button\" class=\"caseXmemo memoButton hidden\"  data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":265,"column":74},"end":{"line":265,"column":85}}}) : helper)))
    + "\"><span>수정</span></button>\r\n			   </div>\r\n			</div>\r\n\r\n			<div class=\"rank\">\r\n				<span>현재 순위</span>\r\n				<div class=\"preview\">\r\n					<button type=\"button\"><span>미리보기</span></button>\r\n					<div>\r\n						<strong>"
    + alias4(((helper = (helper = lookupProperty(helpers,"title") || (depth0 != null ? lookupProperty(depth0,"title") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"title","hash":{},"data":data,"loc":{"start":{"line":274,"column":14},"end":{"line":274,"column":23}}}) : helper)))
    + "</strong>\r\n						<p>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(28, data, 0),"inverse":container.program(5, data, 0),"data":data,"loc":{"start":{"line":276,"column":7},"end":{"line":280,"column":18}}})) != null ? stack1 : "")
    + "						</p>\r\n						<dl class=\"type2\">\r\n							<dt>구매수</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"purchase_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(7, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":283,"column":23},"end":{"line":283,"column":110}}})) != null ? stack1 : "")
    + "</dd>\r\n							<dt>리뷰</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"review_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(11, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":284,"column":22},"end":{"line":284,"column":105}}})) != null ? stack1 : "")
    + "</dd>\r\n							<dt>찜</dt><dd>"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"keep_count") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(13, data, 0),"inverse":container.program(9, data, 0),"data":data,"loc":{"start":{"line":285,"column":21},"end":{"line":285,"column":100}}})) != null ? stack1 : "")
    + "</dd>\r\n						</dl>\r\n\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(15, data, 0),"inverse":container.program(17, data, 0),"data":data,"loc":{"start":{"line":288,"column":6},"end":{"line":292,"column":17}}})) != null ? stack1 : "")
    + "					</div>\r\n				</div>\r\n\r\n				<p>\r\n					<strong>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rank") : depth0),">",0,{"name":"ifCond","hash":{},"fn":container.program(19, data, 0),"inverse":container.program(21, data, 0),"data":data,"loc":{"start":{"line":298,"column":6},"end":{"line":302,"column":17}}})) != null ? stack1 : "")
    + "					</strong>\r\n				</p>\r\n			</div>\r\n\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(23, data, 0),"inverse":container.program(25, data, 0),"data":data,"loc":{"start":{"line":307,"column":3},"end":{"line":311,"column":14}}})) != null ? stack1 : "")
    + "		</a>\r\n\r\n		<div class=\"utilities\">\r\n			<button type=\"button\" class=\"caseXsmall refresh btnRequestRankingPlace\"\r\n				data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":316,"column":13},"end":{"line":316,"column":24}}}) : helper)))
    + "\"\r\n				data-mid=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"mid") || (depth0 != null ? lookupProperty(depth0,"mid") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"mid","hash":{},"data":data,"loc":{"start":{"line":317,"column":14},"end":{"line":317,"column":21}}}) : helper)))
    + "\"\r\n				data-url=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"address") || (depth0 != null ? lookupProperty(depth0,"address") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"address","hash":{},"data":data,"loc":{"start":{"line":318,"column":14},"end":{"line":318,"column":25}}}) : helper)))
    + "\"\r\n				data-keyword=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"keyword") || (depth0 != null ? lookupProperty(depth0,"keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"keyword","hash":{},"data":data,"loc":{"start":{"line":319,"column":18},"end":{"line":319,"column":29}}}) : helper)))
    + "\"\r\n				><span>갱신</span></button>\r\n\r\n			<button type=\"button\" class=\"more\" onclick=\"$(this).next('.functionLayer').toggleClass('showing')\"><span>더보기</span></button>\r\n			<div class=\"functionLayer\" style=\"right: -40px; top: 100px;\">\r\n				<button type=\"button\" class=\"btnDelete\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"rank_id") || (depth0 != null ? lookupProperty(depth0,"rank_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"rank_id","hash":{},"data":data,"loc":{"start":{"line":324,"column":53},"end":{"line":324,"column":64}}}) : helper)))
    + "\">삭제하기</button>\r\n			</div>\r\n		</div>\r\n	</li>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"list") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":1,"column":0},"end":{"line":329,"column":9}}})) != null ? stack1 : "");
},"useData":true});
templates['test'] = template({"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "\r\n<p>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"name") || (depth0 != null ? lookupProperty(depth0,"name") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"name","hash":{},"data":data,"loc":{"start":{"line":2,"column":3},"end":{"line":2,"column":11}}}) : helper)))
    + "</p> 666";
},"useData":true});
templates['tracking'] = template({"1":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "	<!-- item -->\r\n	<li>\r\n		"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"type") : depth0),"==","N",{"name":"ifCond","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":6,"column":2},"end":{"line":6,"column":74}}})) != null ? stack1 : "")
    + "\r\n		"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"type") : depth0),"==","C",{"name":"ifCond","hash":{},"fn":container.program(4, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":7,"column":2},"end":{"line":7,"column":82}}})) != null ? stack1 : "")
    + "\r\n		"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"type") : depth0),"==","P",{"name":"ifCond","hash":{},"fn":container.program(6, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":8,"column":2},"end":{"line":8,"column":80}}})) != null ? stack1 : "")
    + "\r\n			<div class=\"con\">\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"title") : depth0),"!=","",{"name":"ifCond","hash":{},"fn":container.program(8, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":10,"column":3},"end":{"line":12,"column":14}}})) != null ? stack1 : "")
    + "		\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"title") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(10, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":14,"column":3},"end":{"line":16,"column":14}}})) != null ? stack1 : "")
    + "			\r\n			<dl class=\"type2\">\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"type") : depth0),"==","N",{"name":"ifCond","hash":{},"fn":container.program(12, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":19,"column":4},"end":{"line":25,"column":15}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"type") : depth0),"==","C",{"name":"ifCond","hash":{},"fn":container.program(15, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":26,"column":4},"end":{"line":28,"column":15}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"type") : depth0),"==","P",{"name":"ifCond","hash":{},"fn":container.program(17, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":29,"column":4},"end":{"line":34,"column":15}}})) != null ? stack1 : "")
    + "			</dl>\r\n			</div>\r\n			<div class=\"stat\">\r\n			<em>마지막 분석</em>\r\n			<span>"
    + alias4(((helper = (helper = lookupProperty(helpers,"last_date") || (depth0 != null ? lookupProperty(depth0,"last_date") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"last_date","hash":{},"data":data,"loc":{"start":{"line":39,"column":9},"end":{"line":39,"column":22}}}) : helper)))
    + "</span>\r\n			</div>\r\n			\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"==","",{"name":"ifCond","hash":{},"fn":container.program(20, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":42,"column":3},"end":{"line":44,"column":14}}})) != null ? stack1 : "")
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"img") : depth0),"!=","",{"name":"ifCond","hash":{},"fn":container.program(22, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":45,"column":3},"end":{"line":47,"column":14}}})) != null ? stack1 : "")
    + "			\r\n			\r\n		</a>\r\n		<div class=\"utilities\">\r\n			\r\n			<button type=\"button\" class=\"caseXsmall refresh btnRequestTracking\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"tracking_id") || (depth0 != null ? lookupProperty(depth0,"tracking_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"tracking_id","hash":{},"data":data,"loc":{"start":{"line":53,"column":80},"end":{"line":53,"column":95}}}) : helper)))
    + "\" data-type=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"type") || (depth0 != null ? lookupProperty(depth0,"type") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"type","hash":{},"data":data,"loc":{"start":{"line":53,"column":108},"end":{"line":53,"column":116}}}) : helper)))
    + "\" data-address=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"address") || (depth0 != null ? lookupProperty(depth0,"address") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"address","hash":{},"data":data,"loc":{"start":{"line":53,"column":132},"end":{"line":53,"column":143}}}) : helper)))
    + "\"><span>분석</span></button>\r\n			<button type=\"button\" class=\"more\" onclick=\"$(this).next('.functionLayer').toggleClass('showing')\"><span>더보기</span></button>\r\n			<div class=\"functionLayer\" style=\"right: -40px; top: 100px;\">\r\n				<button type=\"button\" class=\"btnDelete\" data-id=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"tracking_id") || (depth0 != null ? lookupProperty(depth0,"tracking_id") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"tracking_id","hash":{},"data":data,"loc":{"start":{"line":56,"column":53},"end":{"line":56,"column":68}}}) : helper)))
    + "\">삭제하기</button>\r\n			</div>\r\n			</div>\r\n	</li>\r\n	<!-- //item -->\r\n";
},"2":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<a href=\"/tracking/"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"tracking_id") || (depth0 != null ? lookupProperty(depth0,"tracking_id") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"tracking_id","hash":{},"data":data,"loc":{"start":{"line":6,"column":46},"end":{"line":6,"column":61}}}) : helper)))
    + "\">";
},"4":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<a href=\"/tracking/coupang/"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"tracking_id") || (depth0 != null ? lookupProperty(depth0,"tracking_id") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"tracking_id","hash":{},"data":data,"loc":{"start":{"line":7,"column":54},"end":{"line":7,"column":69}}}) : helper)))
    + "\">";
},"6":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<a href=\"/tracking/place/"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"tracking_id") || (depth0 != null ? lookupProperty(depth0,"tracking_id") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"tracking_id","hash":{},"data":data,"loc":{"start":{"line":8,"column":52},"end":{"line":8,"column":67}}}) : helper)))
    + "\">";
},"8":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<strong>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"title") || (depth0 != null ? lookupProperty(depth0,"title") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"title","hash":{},"data":data,"loc":{"start":{"line":11,"column":12},"end":{"line":11,"column":21}}}) : helper)))
    + "</strong>\r\n";
},"10":function(container,depth0,helpers,partials,data) {
    return "				<strong>첫 분석 후 표시됩니다. 분석 버튼을 클릭하세요.</strong>\r\n";
},"12":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				\r\n					<b class=\"storeType naver\">스마트스토어</b>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"shop_name") : depth0),"!=","",{"name":"ifCond","hash":{},"fn":container.program(13, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":22,"column":5},"end":{"line":24,"column":16}}})) != null ? stack1 : "");
},"13":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<dt>상점명</dt><dd>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"shop_name") || (depth0 != null ? lookupProperty(depth0,"shop_name") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"shop_name","hash":{},"data":data,"loc":{"start":{"line":23,"column":22},"end":{"line":23,"column":35}}}) : helper)))
    + "</dd>\r\n";
},"15":function(container,depth0,helpers,partials,data) {
    return "					<b class=\"storeType coupang\">쿠팡</b>\r\n";
},"17":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "					<b class=\"storeType naver\">네이버플레이스</b>\r\n"
    + ((stack1 = (lookupProperty(helpers,"ifCond")||(depth0 && lookupProperty(depth0,"ifCond"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"shop_name") : depth0),"!=","",{"name":"ifCond","hash":{},"fn":container.program(18, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":31,"column":5},"end":{"line":33,"column":16}}})) != null ? stack1 : "");
},"18":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<dt>분류</dt><dd>"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"shop_name") || (depth0 != null ? lookupProperty(depth0,"shop_name") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"shop_name","hash":{},"data":data,"loc":{"start":{"line":32,"column":21},"end":{"line":32,"column":34}}}) : helper)))
    + "</dd>\r\n";
},"20":function(container,depth0,helpers,partials,data) {
    return "				<div class=\"thumb\" style=\"background-image: url('/assets/images/no-image-png-2.png');\"><span>썸네일</span></div>\r\n";
},"22":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "				<div class=\"thumb\" style=\"background-image: url('"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"img") || (depth0 != null ? lookupProperty(depth0,"img") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"img","hash":{},"data":data,"loc":{"start":{"line":46,"column":53},"end":{"line":46,"column":60}}}) : helper)))
    + "');\"><span>썸네일</span></div>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<section class=\"analysis\">\r\n	<ul class=\"listProducts case\">\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"list") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":3,"column":1},"end":{"line":61,"column":10}}})) != null ? stack1 : "")
    + "	</ul>\r\n</section>\r\n";
},"useData":true});
templates['tracking_review_analyze'] = template({"1":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "					<tr>\r\n						<td><p class=\"flow\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"category") || (depth0 != null ? lookupProperty(depth0,"category") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"category","hash":{},"data":data,"loc":{"start":{"line":25,"column":26},"end":{"line":25,"column":38}}}) : helper)))
    + "</p></td>\r\n						<td><p class=\"flow\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"headline") || (depth0 != null ? lookupProperty(depth0,"headline") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"headline","hash":{},"data":data,"loc":{"start":{"line":26,"column":26},"end":{"line":26,"column":38}}}) : helper)))
    + "</p></td>\r\n						<td><p class=\"flow\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"benefit") || (depth0 != null ? lookupProperty(depth0,"benefit") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"benefit","hash":{},"data":data,"loc":{"start":{"line":27,"column":26},"end":{"line":27,"column":37}}}) : helper)))
    + "</p></td>\r\n						<td><p class=\"flow\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"risk") || (depth0 != null ? lookupProperty(depth0,"risk") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"risk","hash":{},"data":data,"loc":{"start":{"line":28,"column":26},"end":{"line":28,"column":34}}}) : helper)))
    + "</p></td>\r\n						<td><p class=\"flow\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"audienceHint") || (depth0 != null ? lookupProperty(depth0,"audienceHint") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"audienceHint","hash":{},"data":data,"loc":{"start":{"line":29,"column":26},"end":{"line":29,"column":42}}}) : helper)))
    + "</p></td>\r\n					</tr>\r\n";
},"3":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "		<div class=\"reviewAnalysis\">\r\n		\r\n		<section>\r\n			<h4 class=\"title\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"name") || (depth0 != null ? lookupProperty(depth0,"name") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"name","hash":{},"data":data,"loc":{"start":{"line":41,"column":21},"end":{"line":41,"column":29}}}) : helper)))
    + "</h4>\r\n			<ul>\r\n				<li>\r\n					<strong>긍정적 평가</strong>\r\n					<p>"
    + alias4((lookupProperty(helpers,"textOr")||(depth0 && lookupProperty(depth0,"textOr"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"posSummary") : depth0),"뚜렷한 긍정평가가 없습니다.",{"name":"textOr","hash":{},"data":data,"loc":{"start":{"line":45,"column":8},"end":{"line":45,"column":48}}}))
    + "</p>\r\n				</li>\r\n				<li>\r\n					<strong>부정적 평가</strong>\r\n					<p>"
    + alias4((lookupProperty(helpers,"textOr")||(depth0 && lookupProperty(depth0,"textOr"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"negSummary") : depth0),"뚜렷한 부정평가가 없습니다.",{"name":"textOr","hash":{},"data":data,"loc":{"start":{"line":49,"column":8},"end":{"line":49,"column":48}}}))
    + "</p>\r\n				</li>\r\n			</ul>\r\n			<table class=\"tableOverview\">\r\n				<thead>\r\n					<tr>\r\n					<th scope=\"col\">평점</th>\r\n					<th scope=\"col\">언급</th>\r\n					<th scope=\"col\">긍정</th>\r\n					<th scope=\"col\">부정</th>\r\n					</tr>\r\n				</thead>\r\n				<tbody>\r\n					<tr>\r\n						<td><p class=\"flow\"><b>"
    + alias4((lookupProperty(helpers,"toFixed")||(depth0 && lookupProperty(depth0,"toFixed"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"rating") : depth0),{"name":"toFixed","hash":{},"data":data,"loc":{"start":{"line":63,"column":29},"end":{"line":63,"column":47}}}))
    + "</b></p></td>\r\n						<td><p class=\"flow\"><b>"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"mentionCount") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":64,"column":29},"end":{"line":64,"column":63}}}))
    + "("
    + alias4(((helper = (helper = lookupProperty(helpers,"mentionRate") || (depth0 != null ? lookupProperty(depth0,"mentionRate") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"mentionRate","hash":{},"data":data,"loc":{"start":{"line":64,"column":64},"end":{"line":64,"column":79}}}) : helper)))
    + "%)</b></p></td>\r\n						<td><p class=\"flow\"><b>"
    + alias4(((helper = (helper = lookupProperty(helpers,"posRate") || (depth0 != null ? lookupProperty(depth0,"posRate") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"posRate","hash":{},"data":data,"loc":{"start":{"line":65,"column":29},"end":{"line":65,"column":40}}}) : helper)))
    + "%</b></p></td>\r\n						<td><p class=\"flow\"><b>"
    + alias4(((helper = (helper = lookupProperty(helpers,"negRate") || (depth0 != null ? lookupProperty(depth0,"negRate") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"negRate","hash":{},"data":data,"loc":{"start":{"line":66,"column":29},"end":{"line":66,"column":40}}}) : helper)))
    + "%</b></p></td>\r\n					</tr>\r\n				</tbody>\r\n			</table>\r\n		</section>\r\n		</div>\r\n	\r\n	\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, alias1=depth0 != null ? depth0 : (container.nullContext || {}), lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<div class=\"reviewAnalysis\">\r\n	<section>\r\n		<h4 class=\"title\">종합 분석</h4>\r\n		<ul>\r\n			<li>\r\n				\r\n				<p>"
    + container.escapeExpression((lookupProperty(helpers,"textOr")||(depth0 && lookupProperty(depth0,"textOr"))||container.hooks.helperMissing).call(alias1,((stack1 = (depth0 != null ? lookupProperty(depth0,"pitch") : depth0)) != null ? lookupProperty(stack1,"twoSentence") : stack1),"요약 내용이 없습니다.",{"name":"textOr","hash":{},"data":data,"loc":{"start":{"line":7,"column":7},"end":{"line":7,"column":50}}}))
    + "</p>\r\n			</li>\r\n			\r\n		</ul>\r\n		<table class=\"tableOverview\">\r\n			<thead>\r\n				<tr>\r\n				<th scope=\"col\">분류</th>\r\n				<th scope=\"col\">헤드라인</th>\r\n				<th scope=\"col\">가치</th>\r\n				<th scope=\"col\">우려</th>\r\n				<th scope=\"col\">대상</th>\r\n				\r\n				</tr>\r\n			</thead>\r\n			<tbody>\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,((stack1 = (depth0 != null ? lookupProperty(depth0,"pitch") : depth0)) != null ? lookupProperty(stack1,"points") : stack1),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":23,"column":4},"end":{"line":31,"column":13}}})) != null ? stack1 : "")
    + "				\r\n			</tbody>\r\n		</table>\r\n	</section>\r\n</div>\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(alias1,(depth0 != null ? lookupProperty(depth0,"aspects") : depth0),{"name":"each","hash":{},"fn":container.program(3, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":37,"column":0},"end":{"line":74,"column":9}}})) != null ? stack1 : "")
    + "\r\n\r\n";
},"useData":true});
templates['tracking_review_list_place'] = template({"1":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return ((stack1 = (lookupProperty(helpers,"lt")||(depth0 && lookupProperty(depth0,"lt"))||container.hooks.helperMissing).call(depth0 != null ? depth0 : (container.nullContext || {}),(data && lookupProperty(data,"index")),100,{"name":"lt","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":25,"column":5},"end":{"line":56,"column":12}}})) != null ? stack1 : "");
},"2":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "					<tr>\r\n						<td>\r\n"
    + ((stack1 = lookupProperty(helpers,"if").call(alias1,(depth0 != null ? lookupProperty(depth0,"thumnail") : depth0),{"name":"if","hash":{},"fn":container.program(3, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":28,"column":7},"end":{"line":30,"column":14}}})) != null ? stack1 : "")
    + "						</td>\r\n						<td>\r\n"
    + ((stack1 = (lookupProperty(helpers,"eq")||(depth0 && lookupProperty(depth0,"eq"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"origin_type") : depth0),"영수증",{"name":"eq","hash":{},"fn":container.program(5, data, 0),"inverse":container.program(7, data, 0),"data":data,"loc":{"start":{"line":33,"column":7},"end":{"line":39,"column":14}}})) != null ? stack1 : "")
    + "							<p class=\"flow\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"booking_item_name") || (depth0 != null ? lookupProperty(depth0,"booking_item_name") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"booking_item_name","hash":{},"data":data,"loc":{"start":{"line":40,"column":23},"end":{"line":40,"column":44}}}) : helper)))
    + "</p>\r\n						</td>\r\n\r\n						<td><p class=\"flow\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"nickname") || (depth0 != null ? lookupProperty(depth0,"nickname") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"nickname","hash":{},"data":data,"loc":{"start":{"line":43,"column":26},"end":{"line":43,"column":38}}}) : helper)))
    + "</p></td>\r\n						<td><p class=\"flow\">"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"view_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":44,"column":26},"end":{"line":44,"column":57}}}))
    + "</p></td>\r\n						<td><p class=\"flow\">"
    + alias4((lookupProperty(helpers,"numberWithCommas")||(depth0 && lookupProperty(depth0,"numberWithCommas"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"visit_count") : depth0),{"name":"numberWithCommas","hash":{},"data":data,"loc":{"start":{"line":45,"column":26},"end":{"line":45,"column":58}}}))
    + "</p></td>\r\n\r\n						<td>\r\n							<p class=\"flow\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"create_date") || (depth0 != null ? lookupProperty(depth0,"create_date") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"create_date","hash":{},"data":data,"loc":{"start":{"line":48,"column":23},"end":{"line":48,"column":38}}}) : helper)))
    + "</p>\r\n							<p class=\"flow\">("
    + alias4(((helper = (helper = lookupProperty(helpers,"visit_date") || (depth0 != null ? lookupProperty(depth0,"visit_date") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"visit_date","hash":{},"data":data,"loc":{"start":{"line":49,"column":24},"end":{"line":49,"column":38}}}) : helper)))
    + ")</p>\r\n						</td>\r\n\r\n						<td>\r\n							<a class=\"btnShowReviewContents\" data-contents=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"review_contents") || (depth0 != null ? lookupProperty(depth0,"review_contents") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"review_contents","hash":{},"data":data,"loc":{"start":{"line":53,"column":55},"end":{"line":53,"column":74}}}) : helper)))
    + "\">보기</a>\r\n						</td>\r\n					</tr>\r\n";
},"3":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "								<a href=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"thumnail") || (depth0 != null ? lookupProperty(depth0,"thumnail") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"thumnail","hash":{},"data":data,"loc":{"start":{"line":29,"column":17},"end":{"line":29,"column":29}}}) : helper)))
    + "\" target=\"_blank\"><img src=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"thumnail") || (depth0 != null ? lookupProperty(depth0,"thumnail") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"thumnail","hash":{},"data":data,"loc":{"start":{"line":29,"column":57},"end":{"line":29,"column":69}}}) : helper)))
    + "\" width=\"100\" height=\"100\"></a>\r\n";
},"5":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "								<a href=\""
    + alias4(((helper = (helper = lookupProperty(helpers,"receipt") || (depth0 != null ? lookupProperty(depth0,"receipt") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"receipt","hash":{},"data":data,"loc":{"start":{"line":34,"column":17},"end":{"line":34,"column":28}}}) : helper)))
    + "\" target=\"_blank\" style=\"color:blue;text-decoration: underline;\">\r\n									<p class=\"flow\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"origin_type") || (depth0 != null ? lookupProperty(depth0,"origin_type") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"origin_type","hash":{},"data":data,"loc":{"start":{"line":35,"column":25},"end":{"line":35,"column":40}}}) : helper)))
    + "</p>\r\n								</a>\r\n";
},"7":function(container,depth0,helpers,partials,data) {
    var helper, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "								<p class=\"flow\">"
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"origin_type") || (depth0 != null ? lookupProperty(depth0,"origin_type") : depth0)) != null ? helper : container.hooks.helperMissing),(typeof helper === "function" ? helper.call(depth0 != null ? depth0 : (container.nullContext || {}),{"name":"origin_type","hash":{},"data":data,"loc":{"start":{"line":38,"column":24},"end":{"line":38,"column":39}}}) : helper)))
    + "</p>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<div class=\"reviewAnalysis\">\r\n	<section>\r\n		<h4 class=\"title\"><button type=\"button\" class=\"aside excel btnExcel\">전체 리뷰 다운로드</button></h4>\r\n		<ul>\r\n			<li>\r\n				<p>＊ 웹페이지에는 최신 100개만 표시됩니다. 전체 리뷰는 엑셀파일로 다운로드할수 있습니다.</p>\r\n				<p>＊ 영수증 리뷰의 영수증은 플레이스 소유자만 볼수 있습니다.</p>\r\n			</li>\r\n			\r\n		</ul>\r\n		<table class=\"tableOverview\">\r\n			<thead>\r\n				<tr>\r\n					<th scope=\"col\" width=\"150\"></th>\r\n					<th scope=\"col\" width=\"200\">유형/<br>상품</th>\r\n					<th scope=\"col\" width=\"150\">작성자</th>\r\n					<th scope=\"col\" width=\"100\">노출수</th>\r\n					<th scope=\"col\" width=\"100\">방문횟수</th>\r\n					<th scope=\"col\" width=\"200\">작성일<br>(방문일)</th>\r\n					<th scope=\"col\" width=\"*\">내용</th>\r\n				</tr>\r\n			</thead>\r\n			<tbody>\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),(depth0 != null ? lookupProperty(depth0,"list") : depth0),{"name":"each","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":24,"column":4},"end":{"line":57,"column":13}}})) != null ? stack1 : "")
    + "\r\n			</tbody>\r\n		</table>\r\n	</section>\r\n</div>";
},"useData":true});
templates['tracknig_find_keyword'] = template({"1":function(container,depth0,helpers,partials,data) {
    var stack1, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "					<tr>\r\n"
    + ((stack1 = lookupProperty(helpers,"each").call(depth0 != null ? depth0 : (container.nullContext || {}),depth0,{"name":"each","hash":{},"fn":container.program(2, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":8,"column":5},"end":{"line":10,"column":14}}})) != null ? stack1 : "")
    + "					</tr>\r\n";
},"2":function(container,depth0,helpers,partials,data) {
    var helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, alias3="function", alias4=container.escapeExpression, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "						<th scope=\"col\">"
    + alias4(((helper = (helper = lookupProperty(helpers,"Keyword") || (depth0 != null ? lookupProperty(depth0,"Keyword") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"Keyword","hash":{},"data":data,"loc":{"start":{"line":9,"column":22},"end":{"line":9,"column":33}}}) : helper)))
    + " / "
    + alias4(((helper = (helper = lookupProperty(helpers,"RankingNum") || (depth0 != null ? lookupProperty(depth0,"RankingNum") : depth0)) != null ? helper : alias2),(typeof helper === alias3 ? helper.call(alias1,{"name":"RankingNum","hash":{},"data":data,"loc":{"start":{"line":9,"column":36},"end":{"line":9,"column":50}}}) : helper)))
    + "위</th>\r\n";
},"compiler":[8,">= 4.3.0"],"main":function(container,depth0,helpers,partials,data) {
    var stack1, helper, alias1=depth0 != null ? depth0 : (container.nullContext || {}), alias2=container.hooks.helperMissing, lookupProperty = container.lookupProperty || function(parent, propertyName) {
        if (Object.prototype.hasOwnProperty.call(parent, propertyName)) {
          return parent[propertyName];
        }
        return undefined
    };

  return "<h3 class=\"title\">노출 키워드(조회시간 : "
    + container.escapeExpression(((helper = (helper = lookupProperty(helpers,"updateDate") || (depth0 != null ? lookupProperty(depth0,"updateDate") : depth0)) != null ? helper : alias2),(typeof helper === "function" ? helper.call(alias1,{"name":"updateDate","hash":{},"data":data,"loc":{"start":{"line":1,"column":32},"end":{"line":1,"column":46}}}) : helper)))
    + ")</h3>\r\n<div class=\"reviewAnalysis\">\r\n	<section>\r\n		<table class=\"tableOverview\">\r\n			<thead>\r\n"
    + ((stack1 = (lookupProperty(helpers,"chunk")||(depth0 && lookupProperty(depth0,"chunk"))||alias2).call(alias1,(depth0 != null ? lookupProperty(depth0,"list") : depth0),4,{"name":"chunk","hash":{},"fn":container.program(1, data, 0),"inverse":container.noop,"data":data,"loc":{"start":{"line":6,"column":4},"end":{"line":12,"column":14}}})) != null ? stack1 : "")
    + "			\r\n			</thead>\r\n		</table>\r\n	</section>\r\n</div>\r\n";
},"useData":true});
})();