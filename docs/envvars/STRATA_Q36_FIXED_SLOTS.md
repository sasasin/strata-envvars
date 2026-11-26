# `STRATA_Q36_FIXED_SLOTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6 engine の hybrid expert 配置に対し、実行中の slot 再配置を止めるテスト用スイッチです。設定すると、その時点で各 GPU slot に置かれている expert を `rebalance()` が入れ替えません。未設定時は、ルーティング回数に応じて slot を再配置します。設定は expert の配置選択そのものや routing の記録を止めるものではありません。`Engine::rebalance()` は slot 交換と device slot table 更新を行い、`after_rows()` などから呼ばれます（`engine/src/qwen35/q36_engine.cu:3445-3495`, `1866-1885`）。

この変数が制御するのは card 0 側の hybrid slot 再配置です。peer GPU tier の再配置は別の `STRATA_Q36_PEER_FIXED` 判定を持つ `peer_rebalance()` が担当し、この変数だけでは止まりません（`engine/src/qwen35/q36_engine.cu:3503-3512`）。

## 値と判定

値の内容は parse せず、`std::getenv(...) != nullptr` だけで判定します。したがって未設定なら無効、設定されていれば空文字を含めて有効です。`0`、`false`、大文字表記、前後の空白、その他どの文字列でも「設定あり」となり、無効値はありません（`engine/src/qwen35/q36_engine.cu:3445-3447`）。

| ビルド・実行経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Qwen3.6 engine の hybrid expert 経路 | 再配置を許可 | 空文字、`0`、`false`、その他任意の値 | なし |

CLI 引数や設定ファイルによる同じ判定値の上書きは、この読み取り箇所にはありません。環境変数が存在するかだけを見ます。

## 有効になる条件

- Qwen3.6 engine を使い、expert の一部が GPU slot に、一部が CPU pool に置かれる hybrid モードであること。hybrid は `m.hybrid` が立った場合に設定され、CPU expert pool を含まない build では配置失敗になります（`engine/src/qwen35/q36_engine.cu:4337-4350`）。
- `rebalance()` が呼ばれること。prompt 処理後、decode / verify の 32 position 境界、および batch window の 32 回境界などで呼ばれます（`engine/src/qwen35/q36_engine.cu:1866-1885`, `3743-3749`, `3807-3814`）。
- warmup 中は `warming` によって再配置が抑止されます。設定値は `rebalance()` の最初の呼び出しで cache され、その呼び出しは warmup 中に起こり得るため、プロセス起動時から設定しておく必要があります（`engine/src/qwen35/q36_engine.cu:3445-3448`, `4026-4045`）。
- GPU に全 routed experts が収まり hybrid にならない経路では、この設定による slot 再配置制御は実質的にありません。`rebalance()` は `m->hybrid` が false の場合にも戻ります（`engine/src/qwen35/q36_engine.cu:3445-3448`）。
- `STRATA_Q36_PEER_FIXED` は peer tier の別制御です。peer tier の slot も固定したい場合にこのコード経路で参照されます（`engine/src/qwen35/q36_engine.cu:3506-3512`）。

## 実行時の詳細

関数内の `static const bool off` として初めて `rebalance()` に入った時に環境を読み、そのプロセス内では値を cache します。以後の環境変更は反映されません。設定が存在する場合は `!m->hybrid || off || warming` の条件で早期 return するため、expert profile の dump、slot 交換、device slot table の更新、score の半減処理を行いません（`engine/src/qwen35/q36_engine.cu:3445-3495`）。一方、呼び出し側の `count_rows()` は別に実行されるため routing score は加算されます（`engine/src/qwen35/q36_engine.cu:1872-1884`, `3811-3814`）。

未設定時、再配置処理は各層で routing score 上位の非 resident expert を選び、より score の低い resident expert と交換します。peer GPU がその expert をすでに保持している場合は card 0 側で重複配置しません。host blob を該当 GPU slot にコピーし、host/device の slot 対応表を更新します。1 回の呼び出しでの交換数は caller が渡す上限（通常 8、prompt 後は `hybrid_swaps_after_prompt`）までです（`engine/src/qwen35/q36_engine.cu:3448-3495`, `1881-1885`, `3470-3495`, `3743-3749`）。

## ログと測定値

この変数専用の有効・無効ログはありません。hybrid 実行の終了時には `strata-q36: hybrid experts: ... slot replacements` が stderr に出て、再配置による交換数（`hy_swaps`）を表示します。設定により `rebalance()` が最初から止まっていれば、その交換数は 0 です（`engine/src/qwen35/q36_engine.cu:1837`, `5535-5539`）。この変数に関する測定値は、参照した Strata ソースにありません。

## 根拠

- `engine/src/qwen35/q36_engine.cu:3445-3495` — 設定の読み取り、早期 return、slot 再配置処理。
- `engine/src/qwen35/q36_engine.cu:1866-1885`, `3713-3716`, `3743-3749`, `3807-3814` — score 集計と再配置呼び出し境界。
- `engine/src/qwen35/q36_engine.cu:4026-4045`, `4337-4350` — warmup 抑止と hybrid 条件。
- `engine/src/qwen35/q36_engine.cu:3503-3512`, `5535-5539` — peer 固定判定と終了時の交換数ログ。
