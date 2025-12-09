-- View: public.fprice_optimizer

-- DROP VIEW public.fprice_optimizer;

CREATE OR REPLACE VIEW public.fprice_optimizer
 AS
 WITH params AS (
         SELECT 0.75 AS match_score_threshold
        ), order_item_counts AS (
         SELECT oi.order_id,
            count(DISTINCT oi.id) AS item_count
           FROM order_items oi
          GROUP BY oi.order_id
        ), stocks_filtered AS (
         SELECT s.id,
            s.order_item_id,
            s.lsd_config_id,
            s.found_name,
            s.found_unit,
            s.found_quantity,
            s.price,
            s.fprice,
            s.tprice,
            s.available_stock,
            s.product_url,
            s.product_id_in_lsd,
            s.search_query,
            s.search_result_position,
            s.is_exact_match,
            s.match_score,
            s.created_at,
            s.updated_at,
            s.base_unit,
            s.base_quantity,
            s.min_order_amount,
            s.order_id,
            s.fprice_calculation,
            s.delivery_cost,
            s.delivery_cost_model,
            s.is_alternative,
            s.alternative_for,
            s.requested_quantity,
            s.requested_unit,
            s.max_pieces,
            s.order_item_ids_quantity,
            s.order_item_ids_cost
           FROM lsd_stocks s
             CROSS JOIN params p
          WHERE s.match_score > p.match_score_threshold AND s.order_item_ids_quantity > 0
        ), base AS (
         SELECT sf.id,
            oi.order_id,
            sf.lsd_config_id,
            c.name AS lsd_name,
            oi.id AS order_item_id,
            oi.product_name,
            sf.price,
            sf.fprice,
            sf.base_unit,
            sf.base_quantity,
            COALESCE(sf.fprice::numeric,
                CASE
                    WHEN sf.base_quantity IS DISTINCT FROM 0::numeric THEN sf.price / NULLIF(sf.base_quantity, 0::numeric)
                    ELSE NULL::numeric
                END) AS eff_fprice,
            oi.requested_unit,
            oi.requested_quantity,
            oi.requested_quantity * 1.5 AS over_requested_quantity,
            sf.order_item_ids_quantity,
            sf.order_item_ids_cost,
            min(COALESCE(sf.fprice::numeric,
                CASE
                    WHEN sf.base_quantity IS DISTINCT FROM 0::numeric THEN sf.price / NULLIF(sf.base_quantity, 0::numeric)
                    ELSE NULL::numeric
                END)) OVER (PARTITION BY sf.order_item_id) AS fprice_min,
            COALESCE(sf.fprice::numeric,
                CASE
                    WHEN sf.base_quantity IS DISTINCT FROM 0::numeric THEN sf.price / NULLIF(sf.base_quantity, 0::numeric)
                    ELSE NULL::numeric
                END) - min(COALESCE(sf.fprice::numeric,
                CASE
                    WHEN sf.base_quantity IS DISTINCT FROM 0::numeric THEN sf.price / NULLIF(sf.base_quantity, 0::numeric)
                    ELSE NULL::numeric
                END)) OVER (PARTITION BY sf.order_item_id) AS fprice_diff,
            (COALESCE(sf.fprice::numeric,
                CASE
                    WHEN sf.base_quantity IS DISTINCT FROM 0::numeric THEN sf.price / NULLIF(sf.base_quantity, 0::numeric)
                    ELSE NULL::numeric
                END) - min(COALESCE(sf.fprice::numeric,
                CASE
                    WHEN sf.base_quantity IS DISTINCT FROM 0::numeric THEN sf.price / NULLIF(sf.base_quantity, 0::numeric)
                    ELSE NULL::numeric
                END)) OVER (PARTITION BY sf.order_item_id)) * sf.base_quantity AS loss,
            COALESCE(c.min_order_amount, sf.min_order_amount) AS min_order_amount,
            sf.delivery_cost_model,
            c.delivery_fixed_fee,
            row_number() OVER (PARTITION BY oi.id, sf.lsd_config_id ORDER BY (COALESCE(sf.fprice::numeric,
                CASE
                    WHEN sf.base_quantity IS DISTINCT FROM 0::numeric THEN sf.price / NULLIF(sf.base_quantity, 0::numeric)
                    ELSE NULL::numeric
                END)), sf.price, sf.id) AS rownum_by_lsd,
            oic.item_count,
                CASE
                    WHEN oic.item_count = 1 THEN 100
                    WHEN oic.item_count = 2 THEN 50
                    WHEN oic.item_count = 3 THEN 50
                    WHEN oic.item_count = 4 THEN 30
                    WHEN oic.item_count = 5 THEN 15
                    WHEN oic.item_count = 6 THEN 10
                    WHEN oic.item_count = 7 THEN 7
                    WHEN oic.item_count = 8 THEN 5
                    WHEN oic.item_count = 9 THEN 4
                    WHEN oic.item_count = 10 THEN 4
                    ELSE LEAST(5, floor(power(5000000::numeric / oic.item_count::numeric, 1.0 / oic.item_count::numeric))::integer)
                END AS max_variants_per_item
           FROM stocks_filtered sf
             JOIN lsd_configs c ON c.id = sf.lsd_config_id
             JOIN order_items oi ON oi.id = sf.order_item_id
             JOIN order_item_counts oic ON oic.order_id = oi.order_id
        ), shop_best AS (
         SELECT b.id,
            b.order_id,
            b.lsd_config_id,
            b.lsd_name,
            b.order_item_id,
            b.product_name,
            b.price,
            b.fprice,
            b.base_unit,
            b.base_quantity,
            b.eff_fprice,
            b.requested_unit,
            b.requested_quantity,
            b.over_requested_quantity,
            b.order_item_ids_quantity,
            b.order_item_ids_cost,
            b.fprice_min,
            b.fprice_diff,
            b.loss,
            b.min_order_amount,
            b.delivery_cost_model,
            b.delivery_fixed_fee,
            b.rownum_by_lsd,
            b.item_count,
            b.max_variants_per_item
           FROM base b
          WHERE b.rownum_by_lsd = 1
        ), limit_per_item AS (
         SELECT base.order_item_id,
            max(base.max_variants_per_item) AS limit_per_item
           FROM base
          GROUP BY base.order_item_id
        ), shop_best_ranked AS (
         SELECT sb.id,
            sb.order_id,
            sb.lsd_config_id,
            sb.lsd_name,
            sb.order_item_id,
            sb.product_name,
            sb.price,
            sb.fprice,
            sb.base_unit,
            sb.base_quantity,
            sb.eff_fprice,
            sb.requested_unit,
            sb.requested_quantity,
            sb.over_requested_quantity,
            sb.order_item_ids_quantity,
            sb.order_item_ids_cost,
            sb.fprice_min,
            sb.fprice_diff,
            sb.loss,
            sb.min_order_amount,
            sb.delivery_cost_model,
            sb.delivery_fixed_fee,
            sb.rownum_by_lsd,
            sb.item_count,
            sb.max_variants_per_item,
            row_number() OVER (PARTITION BY sb.order_item_id ORDER BY sb.eff_fprice, sb.price, sb.id) AS shop_rank
           FROM shop_best sb
        ), final AS (
         SELECT sbr.id,
            sbr.order_id,
            sbr.lsd_config_id,
            sbr.lsd_name,
            sbr.order_item_id,
            sbr.product_name,
            sbr.price,
            sbr.fprice,
            sbr.base_unit,
            sbr.base_quantity,
            sbr.eff_fprice,
            sbr.requested_unit,
            sbr.requested_quantity,
            sbr.over_requested_quantity,
            sbr.order_item_ids_quantity,
            sbr.order_item_ids_cost,
            sbr.fprice_min,
            sbr.fprice_diff,
            sbr.loss,
            sbr.min_order_amount,
            sbr.delivery_cost_model,
            sbr.delivery_fixed_fee,
            sbr.rownum_by_lsd,
            sbr.item_count,
            sbr.max_variants_per_item,
            sbr.shop_rank
           FROM shop_best_ranked sbr
             JOIN limit_per_item l ON l.order_item_id = sbr.order_item_id
          WHERE sbr.shop_rank <= l.limit_per_item
        )
 SELECT f.id,
    f.order_id,
    f.lsd_config_id,
    f.lsd_name,
    f.order_item_id,
    f.product_name,
    f.price,
    f.fprice,
    f.base_unit,
    f.base_quantity,
    f.requested_unit,
    f.requested_quantity,
    f.order_item_ids_quantity,
    f.order_item_ids_cost,
    f.fprice_min,
    f.fprice_diff,
    f.loss,
    f.min_order_amount,
    f.delivery_cost_model,
    f.delivery_fixed_fee,
    f.over_requested_quantity,
    f.item_count AS items_in_order,
    f.max_variants_per_item AS variants_limit
   FROM final f
  ORDER BY f.order_id, f.order_item_id, f.eff_fprice, f.price, f.id;

ALTER TABLE public.fprice_optimizer
    OWNER TO korzinka_user;
COMMENT ON VIEW public.fprice_optimizer
    IS 'По каждому товару: не более max_variants_per_item; по одному лучшему офферу на магазин (минимальный eff_fprice); если магазинов > лимита — топ-K по eff_fprice.';

