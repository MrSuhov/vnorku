-- Добавление fprice в результаты процедуры top_baskets

CREATE OR REPLACE FUNCTION public.top_baskets(p_order_id integer, p_rank integer)
RETURNS TABLE(
    result_type text, 
    lsd_name character varying, 
    product_name character varying, 
    original_product_name character varying, 
    base_quantity numeric, 
    base_unit character varying, 
    price numeric, 
    fprice numeric,  -- ДОБАВЛЕНО
    order_item_ids_cost numeric, 
    order_item_ids_quantity numeric, 
    requested_quantity numeric, 
    requested_unit character varying, 
    product_url character varying, 
    order_id integer, 
    basket_rank integer, 
    total_goods_cost numeric, 
    total_delivery_cost numeric, 
    total_loss numeric, 
    total_cost numeric, 
    diff_with_rank1 numeric
)
LANGUAGE plpgsql
AS $function$
DECLARE
    v_basket_id INTEGER;
    v_rank1_total_cost NUMERIC(10,2);
    v_current_total_cost NUMERIC(10,2);
BEGIN
    -- Находим basket_id для указанного ранга
    SELECT ba.basket_id
    INTO v_basket_id
    FROM basket_analyses ba
    WHERE ba.order_id = p_order_id
      AND ba.basket_rank = p_rank;
    
    -- Если корзина не найдена, возвращаем пустой результат
    IF v_basket_id IS NULL THEN
        RAISE NOTICE 'Basket with order_id=% and rank=% not found', p_order_id, p_rank;
        RETURN;
    END IF;
    
    -- Получаем стоимость корзины с рангом 1 для расчета разницы
    SELECT ba.total_cost
    INTO v_rank1_total_cost
    FROM basket_analyses ba
    WHERE ba.order_id = p_order_id
      AND ba.basket_rank = 1;
    
    -- Получаем стоимость текущей корзины
    SELECT ba.total_cost
    INTO v_current_total_cost
    FROM basket_analyses ba
    WHERE ba.basket_id = v_basket_id;
    
    -- Result Set 1: Детализация товаров, сгруппированная по магазинам
    RETURN QUERY
    SELECT
        'ITEMS'::TEXT as result_type,
        bc.lsd_name,
        bc.product_name,
        oi.product_name as original_product_name,
        bc.base_quantity,
        bc.base_unit,
        bc.price,
        bc.fprice,  -- ДОБАВЛЕНО
        bc.order_item_ids_cost,
        bc.order_item_ids_quantity,
        oi.requested_quantity,
        oi.requested_unit,
        ls.product_url,
        -- Сводные поля NULL для детализации
        NULL::INTEGER as order_id,
        NULL::INTEGER as basket_rank,
        NULL::NUMERIC(10,2) as total_goods_cost,
        NULL::NUMERIC(10,2) as total_delivery_cost,
        NULL::NUMERIC(10,2) as total_loss,
        NULL::NUMERIC(10,2) as total_cost,
        NULL::NUMERIC(10,2) as diff_with_rank1
    FROM basket_combinations bc
    INNER JOIN order_items oi ON bc.order_item_id = oi.id
    LEFT JOIN lsd_stocks ls ON bc.fprice_optimizer_id = ls.id
    WHERE bc.basket_id = v_basket_id
    ORDER BY bc.lsd_name, bc.order_item_id;
    
    -- Result Set 2: Сводная информация
    RETURN QUERY
    SELECT
        'SUMMARY'::TEXT as result_type,
        -- Детальные поля NULL для сводки
        NULL::VARCHAR(100) as lsd_name,
        NULL::VARCHAR(500) as product_name,
        NULL::VARCHAR(500) as original_product_name,
        NULL::NUMERIC(10,3) as base_quantity,
        NULL::VARCHAR(10) as base_unit,
        NULL::NUMERIC(10,2) as price,
        NULL::NUMERIC(10,2) as fprice,  -- ДОБАВЛЕНО
        NULL::NUMERIC(10,2) as order_item_ids_cost,
        NULL::NUMERIC as order_item_ids_quantity,
        NULL::NUMERIC(10,3) as requested_quantity,
        NULL::VARCHAR(20) as requested_unit,
        NULL::VARCHAR(1000) as product_url,
        -- Сводные поля
        ba.order_id,
        ba.basket_rank,
        ba.total_goods_cost,
        ba.total_delivery_cost,
        ba.total_loss,
        ba.total_cost,
        CASE 
            WHEN p_rank = 1 THEN 0.00
            ELSE (v_current_total_cost - COALESCE(v_rank1_total_cost, 0.00))
        END as diff_with_rank1
    FROM basket_analyses ba
    WHERE ba.basket_id = v_basket_id;
    
END;
$function$;

COMMENT ON FUNCTION public.top_baskets(integer, integer) IS 
'Возвращает детализацию корзины по рангу с fprice для отображения цены за единицу';
