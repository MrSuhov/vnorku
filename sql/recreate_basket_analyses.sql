-- Полная переработка таблицы basket_analyses

-- Удаляем зависимые объекты
DROP VIEW IF EXISTS v_basket_analysis_summary CASCADE;
DROP VIEW IF EXISTS v_basket_analyses_ranked CASCADE;
DROP FUNCTION IF EXISTS get_basket_analysis_results CASCADE;

-- Пересоздаем таблицу basket_analyses с правильной структурой
DROP TABLE IF EXISTS basket_analyses CASCADE;

CREATE TABLE basket_analyses (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    basket_id INTEGER NOT NULL,
    total_loss NUMERIC(10,2) DEFAULT 0,
    total_goods_cost NUMERIC(10,2) DEFAULT 0,
    delivery_cost JSON,
    delivery_topup JSON,
    total_delivery_cost NUMERIC(10,2) DEFAULT 0,
    total_cost NUMERIC(10,2) DEFAULT 0,
    total_loss_and_delivery NUMERIC(10,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Уникальный индекс на комбинацию order_id и basket_id
    UNIQUE(order_id, basket_id)
);

-- Создаем индексы
CREATE INDEX idx_basket_analyses_order_id ON basket_analyses(order_id);
CREATE INDEX idx_basket_analyses_total_loss_and_delivery ON basket_analyses(total_loss_and_delivery);

-- Процедура для анализа ВСЕХ корзин заказа
CREATE OR REPLACE PROCEDURE analyze_order_baskets(
    p_order_id INTEGER
) AS $$
DECLARE
    v_basket RECORD;
    v_delivery_cost JSON;
    v_delivery_topup JSON;
    v_total_delivery_cost NUMERIC(10,2);
BEGIN
    -- Проверяем, что order_id указан
    IF p_order_id IS NULL THEN
        RAISE EXCEPTION 'order_id is required';
    END IF;
    
    -- Сначала рассчитываем стоимость доставки для всех корзин заказа
    CALL calculate_basket_delivery_costs(p_order_id);
    
    -- Удаляем старые записи анализа для этого заказа
    DELETE FROM basket_analyses WHERE order_id = p_order_id;
    
    -- Обрабатываем каждую корзину заказа
    FOR v_basket IN 
        SELECT 
            bc.basket_id,
            bc.order_id,
            -- Суммарные данные по корзине
            SUM(bc.loss) as total_loss,
            SUM(bc.order_item_ids_cost) as total_goods_cost
        FROM basket_combinations bc
        WHERE bc.order_id = p_order_id
        GROUP BY bc.basket_id, bc.order_id
    LOOP
        -- Получаем JSON с доставкой и топапами для этой корзины
        SELECT 
            json_object_agg(
                COALESCE(lc.name, bcc.lsd_name), 
                bdc.delivery_cost
            ),
            json_object_agg(
                COALESCE(lc.name, bcc.lsd_name), 
                bdc.topup
            ),
            SUM(bdc.delivery_cost) as total_delivery
        INTO 
            v_delivery_cost,
            v_delivery_topup,
            v_total_delivery_cost
        FROM basket_delivery_costs bdc
        LEFT JOIN lsd_configs lc ON lc.id = bdc.lsd_config_id
        LEFT JOIN (
            SELECT DISTINCT basket_id, lsd_config_id, lsd_name 
            FROM basket_combinations
            WHERE basket_id = v_basket.basket_id
        ) bcc ON bcc.lsd_config_id = bdc.lsd_config_id
        WHERE bdc.basket_id = v_basket.basket_id;
        
        -- Вставляем запись для этой корзины
        INSERT INTO basket_analyses (
            order_id,
            basket_id,
            total_loss,
            total_goods_cost,
            delivery_cost,
            delivery_topup,
            total_delivery_cost,
            total_cost,
            total_loss_and_delivery
        ) VALUES (
            v_basket.order_id,
            v_basket.basket_id,
            COALESCE(v_basket.total_loss, 0),
            COALESCE(v_basket.total_goods_cost, 0),
            COALESCE(v_delivery_cost, '{}'::JSON),
            COALESCE(v_delivery_topup, '{}'::JSON),
            COALESCE(v_total_delivery_cost, 0),
            COALESCE(v_basket.total_goods_cost, 0) + COALESCE(v_total_delivery_cost, 0),
            COALESCE(v_basket.total_loss, 0) + COALESCE(v_total_delivery_cost, 0)
        );
    END LOOP;
    
    -- Выводим результат
    RAISE NOTICE 'Анализ завершен для заказа %. Обработано корзин: %', 
        p_order_id,
        (SELECT COUNT(*) FROM basket_analyses WHERE order_id = p_order_id);
    
    RAISE NOTICE 'Лучшая корзина: % (потери+доставка: %₽)', 
        (SELECT basket_id FROM basket_analyses 
         WHERE order_id = p_order_id 
         ORDER BY total_loss_and_delivery ASC 
         LIMIT 1),
        (SELECT total_loss_and_delivery FROM basket_analyses 
         WHERE order_id = p_order_id 
         ORDER BY total_loss_and_delivery ASC 
         LIMIT 1);
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Ошибка при анализе заказа %: %', p_order_id, SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- View для удобного просмотра с рангами
CREATE OR REPLACE VIEW v_basket_analyses_ranked AS
SELECT 
    ba.*,
    ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY total_loss_and_delivery ASC) as rank,
    FIRST_VALUE(basket_id) OVER (PARTITION BY order_id ORDER BY total_loss_and_delivery ASC) as best_basket_id,
    LAST_VALUE(basket_id) OVER (PARTITION BY order_id ORDER BY total_loss_and_delivery ASC 
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as worst_basket_id
FROM basket_analyses ba
ORDER BY order_id, total_loss_and_delivery ASC;

-- Функция для получения топ N корзин заказа
CREATE OR REPLACE FUNCTION get_top_baskets_for_order(
    p_order_id INTEGER,
    p_limit INTEGER DEFAULT 10
) RETURNS TABLE (
    rank BIGINT,
    basket_id INTEGER,
    total_loss NUMERIC(10,2),
    total_goods_cost NUMERIC(10,2),
    delivery_cost JSON,
    delivery_topup JSON,
    total_delivery_cost NUMERIC(10,2),
    total_cost NUMERIC(10,2),
    total_loss_and_delivery NUMERIC(10,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ROW_NUMBER() OVER (ORDER BY ba.total_loss_and_delivery ASC) as rank,
        ba.basket_id,
        ba.total_loss,
        ba.total_goods_cost,
        ba.delivery_cost,
        ba.delivery_topup,
        ba.total_delivery_cost,
        ba.total_cost,
        ba.total_loss_and_delivery
    FROM basket_analyses ba
    WHERE ba.order_id = p_order_id
    ORDER BY ba.total_loss_and_delivery ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Функция для получения сводной статистики по заказу
CREATE OR REPLACE FUNCTION get_order_analysis_summary(
    p_order_id INTEGER
) RETURNS TABLE (
    order_id INTEGER,
    total_baskets BIGINT,
    best_basket_id INTEGER,
    best_total_cost NUMERIC(10,2),
    worst_basket_id INTEGER,
    worst_total_cost NUMERIC(10,2),
    avg_total_cost NUMERIC(10,2),
    potential_savings NUMERIC(10,2),
    baskets_with_free_delivery BIGINT,
    baskets_with_topup BIGINT
) AS $$
BEGIN
    RETURN QUERY
    WITH summary AS (
        SELECT 
            ba.order_id,
            COUNT(*) as total_baskets,
            MIN(ba.basket_id) FILTER (WHERE ba.total_loss_and_delivery = MIN(ba.total_loss_and_delivery) OVER()) as best_basket,
            MIN(ba.total_cost) as best_cost,
            MAX(ba.basket_id) FILTER (WHERE ba.total_loss_and_delivery = MAX(ba.total_loss_and_delivery) OVER()) as worst_basket,
            MAX(ba.total_cost) as worst_cost,
            AVG(ba.total_cost) as avg_cost,
            MAX(ba.total_cost) - MIN(ba.total_cost) as savings
        FROM basket_analyses ba
        WHERE ba.order_id = p_order_id
        GROUP BY ba.order_id
    ),
    delivery_stats AS (
        SELECT 
            ba.order_id,
            COUNT(*) FILTER (WHERE ba.total_delivery_cost = 0) as free_delivery_count,
            COUNT(*) FILTER (WHERE ba.delivery_topup::text != '{}') as topup_count
        FROM basket_analyses ba
        WHERE ba.order_id = p_order_id
        GROUP BY ba.order_id
    )
    SELECT 
        s.order_id,
        s.total_baskets,
        s.best_basket,
        s.best_cost,
        s.worst_basket,
        s.worst_cost,
        s.avg_cost,
        s.savings,
        d.free_delivery_count,
        d.topup_count
    FROM summary s
    JOIN delivery_stats d ON d.order_id = s.order_id;
END;
$$ LANGUAGE plpgsql;
