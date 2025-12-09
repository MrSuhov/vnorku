-- Fix top_baskets function - cast basket_id to BIGINT to match return type

DROP FUNCTION IF EXISTS top_baskets(integer, integer) CASCADE;

CREATE OR REPLACE FUNCTION public.top_baskets(p_order_id integer, p_rank integer)
 RETURNS TABLE(
   result_type text,
   lsd_name character varying,
   product_name character varying,
   original_product_name character varying,
   base_quantity numeric,
   base_unit character varying,
   price numeric,
   fprice numeric,
   loss numeric,
   order_item_ids_cost numeric,
   order_item_ids_quantity numeric,
   requested_quantity numeric,
   requested_unit character varying,
   product_url character varying,
   delivery_cost numeric,
   topup numeric,
   basket_id bigint,
   order_id bigint,
   basket_rank integer,
   total_goods_cost numeric,
   total_delivery_cost numeric,
   total_loss numeric,
   total_cost numeric,
   total_loss_and_delivery numeric,
   diff_with_rank1 numeric,
   delivery_topup json
 )
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_basket_id INTEGER;  -- Changed from BIGINT to match actual table type
    v_rank1_loss_and_delivery NUMERIC(10,2);
    v_current_loss_and_delivery NUMERIC(10,2);
BEGIN
    SELECT ba.basket_id
    INTO v_basket_id
    FROM basket_analyses ba
    WHERE ba.order_id = p_order_id
      AND ba.basket_rank = p_rank;

    IF v_basket_id IS NULL THEN
        RAISE NOTICE 'Basket with order_id=% and rank=% not found', p_order_id, p_rank;
        RETURN;
    END IF;

    SELECT ba.total_loss_and_delivery
    INTO v_rank1_loss_and_delivery
    FROM basket_analyses ba
    WHERE ba.order_id = p_order_id
      AND ba.basket_rank = 1;

    SELECT ba.total_loss_and_delivery
    INTO v_current_loss_and_delivery
    FROM basket_analyses ba
    WHERE ba.basket_id = v_basket_id
      AND ba.order_id = p_order_id;

    -- FIXED: JOIN with lsd_stocks to get product_url
    RETURN QUERY
    SELECT
        'ITEMS'::TEXT as result_type,
        bc.lsd_name,
        bc.product_name,
        oi.product_name as original_product_name,
        bc.base_quantity,
        bc.base_unit,
        bc.price,
        bc.fprice,
        bc.loss,
        bc.order_item_ids_cost,
        bc.order_item_ids_quantity,
        oi.requested_quantity,
        oi.requested_unit,
        ls.product_url,  -- FIXED: Get from lsd_stocks instead of NULL
        NULL::NUMERIC(10,2) as delivery_cost,
        NULL::NUMERIC(10,2) as topup,
        bc.basket_id::BIGINT,  -- FIXED: Cast to BIGINT
        bc.order_id::BIGINT,   -- FIXED: Cast to BIGINT
        NULL::INTEGER as basket_rank,
        NULL::NUMERIC(10,2) as total_goods_cost,
        NULL::NUMERIC(10,2) as total_delivery_cost,
        NULL::NUMERIC(10,2) as total_loss,
        NULL::NUMERIC(10,2) as total_cost,
        NULL::NUMERIC(10,2) as total_loss_and_delivery,
        NULL::NUMERIC(10,2) as diff_with_rank1,
        NULL::JSON as delivery_topup
    FROM basket_combinations bc
    JOIN order_items oi ON oi.id = bc.order_item_id
    LEFT JOIN lsd_stocks ls ON ls.id = bc.lsd_stock_id  -- FIXED: JOIN to get product_url
    WHERE bc.basket_id = v_basket_id
      AND bc.order_id = p_order_id
    ORDER BY bc.lsd_name, bc.product_name;

    -- FIXED: Add DELIVERY_DETAILS rows
    RETURN QUERY
    SELECT
        'DELIVERY_DETAILS'::TEXT as result_type,
        lsd.name as lsd_name,
        NULL::VARCHAR(500) as product_name,
        NULL::VARCHAR(500) as original_product_name,
        NULL::NUMERIC(10,3) as base_quantity,
        NULL::VARCHAR(10) as base_unit,
        NULL::NUMERIC(10,2) as price,
        NULL::NUMERIC(10,2) as fprice,
        NULL::NUMERIC(10,2) as loss,
        NULL::NUMERIC(10,2) as order_item_ids_cost,
        NULL::NUMERIC as order_item_ids_quantity,
        NULL::NUMERIC(10,3) as requested_quantity,
        NULL::VARCHAR(20) as requested_unit,
        NULL::VARCHAR(1000) as product_url,
        bdc.delivery_cost,
        bdc.topup,
        NULL::BIGINT as basket_id,
        NULL::BIGINT as order_id,
        NULL::INTEGER as basket_rank,
        NULL::NUMERIC(10,2) as total_goods_cost,
        NULL::NUMERIC(10,2) as total_delivery_cost,
        NULL::NUMERIC(10,2) as total_loss,
        NULL::NUMERIC(10,2) as total_cost,
        NULL::NUMERIC(10,2) as total_loss_and_delivery,
        NULL::NUMERIC(10,2) as diff_with_rank1,
        NULL::JSON as delivery_topup
    FROM basket_delivery_costs bdc
    JOIN lsd_configs lsd ON lsd.id = bdc.lsd_config_id
    WHERE bdc.basket_id = v_basket_id
      AND bdc.order_id = p_order_id
    ORDER BY lsd.name;

    RETURN QUERY
    SELECT
        'SUMMARY'::TEXT as result_type,
        NULL::VARCHAR(100) as lsd_name,
        NULL::VARCHAR(500) as product_name,
        NULL::VARCHAR(500) as original_product_name,
        NULL::NUMERIC(10,3) as base_quantity,
        NULL::VARCHAR(10) as base_unit,
        NULL::NUMERIC(10,2) as price,
        NULL::NUMERIC(10,2) as fprice,
        NULL::NUMERIC(10,2) as loss,
        NULL::NUMERIC(10,2) as order_item_ids_cost,
        NULL::NUMERIC as order_item_ids_quantity,
        NULL::NUMERIC(10,3) as requested_quantity,
        NULL::VARCHAR(20) as requested_unit,
        NULL::VARCHAR(1000) as product_url,
        NULL::NUMERIC(10,2) as delivery_cost,
        NULL::NUMERIC(10,2) as topup,
        ba.basket_id::BIGINT,  -- FIXED: Cast to BIGINT
        ba.order_id::BIGINT,   -- FIXED: Cast to BIGINT
        ba.basket_rank,
        ba.total_goods_cost,
        ba.total_delivery_cost,
        ba.total_loss,
        ba.total_cost,
        ba.total_loss_and_delivery,
        CASE
            WHEN p_rank = 1 THEN 0.00
            ELSE (v_current_loss_and_delivery - COALESCE(v_rank1_loss_and_delivery, 0.00))
        END as diff_with_rank1,
        ba.delivery_topup
    FROM basket_analyses ba
    WHERE ba.basket_id = v_basket_id
      AND ba.order_id = p_order_id;
END;
$function$;
