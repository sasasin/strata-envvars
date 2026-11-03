# `FNX_NO_TWIN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next (`src/split`) エンジンの decode 用 Q8_1 activation buffer に対する「split twin」の登録を止めます。未設定なら、各カードの `xq` と `sh_hq` に通常の Q8_1 バッファに加えて split twin 用の device buffer を割り当て、registry に登録します。設定されている場合はこの登録と追加割り当てを省きます。これはエンジンの decode バッファ用の条件で、環境変数名から想像される全 Q8_1 twin の一括無効化ではありません。

## 値と判定

`std::getenv("FNX_NO_TWIN")` の null 判定だけで、値を parse しません。

| 状態 | 判定・動作 |
|---|---|
| 未設定 | 条件が真になり、`xq` と `sh_hq` の twin buffers を割り当てて登録 |
| 設定あり | 条件が偽になり、両 buffer の twin 登録を省略 |
| 空文字 | 設定ありとして登録を省略 |
| その他の値 | 内容にかかわらず設定ありとして登録を省略。`0` も無効化しない |

CLI 引数や別の環境変数との優先順位、値の境界・無効値 fallback はありません。値は boolean として変換されず、設定有無のみが使われます。

## 有効になる条件

この参照は `src/split/src/engine.cu` の Flash-Next `Engine` 構築中に行われ、カードごとの `CardBuf` 初期化で評価されます（`engine.cu:31,114-120,175-179`）。呼び出しごとに環境を読み、static cache はありません。通常の実行では engine 構築後に変更しても、すでに初期化されたバッファの登録状態は変わりません。

`FNX_PF_MOE_Q8` が prompt 側で Q8 MoE prefill を有効にすると、prefill 用 `p->xq` は別のコードで twin 登録されます。`FNX_NO_TWIN` はその登録を抑止しません (`src/split/src/prefill.cu:721-726`)。この変数の直接参照は `src/split/src/engine.cu:175` のみで、候補名の完全一致検索では他の Strata ソース参照は見つかりませんでした。

## 実行時の詳細

未設定の経路では `q8_twin` が Q8_1 buffer の範囲と twin pointers を registry に加え、量子化 kernel は通常の Q8_1 データに加えて twin にも値と scale を書きます (`src/split/src/engine.cu:175-179`; `src/split/src/kernels.cu:1051-1067,117-130`)。登録された twin は scope 解放時に `q8_untwin` で registry から外されます (`engine.cu:179`, `kernels.cu:1056-1060`)。

`FNX_NO_TWIN` が設定されている場合、これらの engine decode buffer は registry に見つかりません。kernel の `twin_of` は初期値を null にし、登録範囲に一致した場合だけ twin pointers を返します。Q8S kernel は twin pointer の有無で split (`true`) と通常 (`false`) の実装を選びます (`src/split/src/kernels.cu:102-115,2228-2235`)。ヘッダーの実装コメントも、twin を Q8_1 activation buffer の split 表現として説明しています (`src/split/src/kernels.hpp:42-47`)。

この分岐自体に `FNX_NO_TWIN` 固有のログ、警告、終了・失敗処理はありません。twin 用追加割り当てを通らないため、その割り当てに起因する失敗経路も通りませんが、性能や生成結果の差はこのコード調査だけでは断定しません。

## 根拠

- 候補名の全参照検索: `src/split/src/engine.cu:175` のみ。
- 判定と engine twin buffer 登録・解放: `src/split/src/engine.cu:114-120,170-180`。
- registry 検索、量子化時の twin 書き込み、登録・解除: `src/split/src/kernels.cu:102-115,117-130,1051-1067`。
- twin 有無による kernel 経路選択: `src/split/src/kernels.cu:2228-2235`。
- prefill 側の別登録条件: `src/split/src/prefill.cu:721-726`。
