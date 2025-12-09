SELECT * FROM public.users  --waiting_address --address
SELECT * FROM public.user_sessions --where user_name ~* 'Serg' -- session_type sms_code default_delivery_address
SELECT * FROM public.orders -- analyzing -- optimized --optimizing --analysis_complete results_sent_at
SELECT * FROM public.order_items

SELECT * FROM public.lsd_configs --WHERE is_mvp --search_config_rpa
public.fprice_optimizer
SELECT name, ls.* FROM public.lsd_stocks ls join lsd_configs l on lsd_config_id = l.id where 1=1
and order_id=33
-- and name = 'vkusvill'
and match_score>0.75 
order by order_item_id, fprice 

SELECT l.name, count(distinct order_item_id) FROM lsd_stocks join lsd_configs l on lsd_config_id = l.id where order_id=25 and match_score>0.75 group by l.name
SELECT ls.search_query, count(*), string_agg(distinct l.name, ',') FROM lsd_stocks ls join lsd_configs l on lsd_config_id = l.id where order_id=25 and match_score>0.75 and order_item_ids_quantity > 0 group by search_query

SELECT json_agg(row_to_json(t)) FROM (SELECT * FROM public.lsd_stocks WHERE id = 34874) t;
SELECT json_agg(row_to_json(t)) FROM (SELECT * FROM public.basket_combinations WHERE basket_id = 145192 and order_id=23) t;
SELECT json_agg(row_to_json(t)) FROM (SELECT * FROM public.fprice_optimizer) t;


SELECT * FROM fprice_lsd_order where order_id=36 order by requested_product, fprice asc
SELECT * FROM public.fprice_optimizer where order_id=36
SELECT order_item_id, count(*) FROM public.fprice_optimizer where order_id=34 group by order_item_id

-- call public.generate_best_basket_combinations(16, p_top_variants_per_item)
-- call public.generate_basket_combinations(16)
-- call public.calculate_basket_delivery_costs(16)
-- call public.analyze_order_baskets(16)
SELECT * FROM public.basket_combinations where order_id = 30 --and basket_id in (145192, 145434) order by product_name
SELECT * FROM public.basket_delivery_costs where order_id = 30
SELECT * FROM public.basket_analyses where order_id = 30 and basket_id = 1
SELECT * FROM public.basket_analyses where order_id = 20 order by total_loss_and_delivery limit 5
SELECT count(*) FROM public.basket_combinations
SELECT count(*) FROM public.basket_delivery_costs

SELECT * FROM public.top_baskets_detailed

delivery_cost_model
min_order_amount

order_item_ids_quantity
total_delivery_cost = delivery_cost + delivery_topup
order_item_ids_cost
lsd_total_basket_cost
public.basket_analyses
is_mvp = true
user_name
match_score
search_result_position
original_text
public.order_items
product_url
search_config_rpa
found_quantity
found_unit
telegram_message_id
free_delivery_threshold
delivery_fee

tprice
product_id_in_lsd
search_result_position
max_pieces
