# `STRATA_VERIFY_DEBUG`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Verifier の進行状況や、SYCL の verifier window に残った中間値を stderr に出す診断用スイッチです。推論結果を選ぶ条件ではなく、CUDA/HIP では主に capture・staging・layer handshake のログを追加します。SYCL では同じ進行ログに加え、条件付きで layer ごとの residual `R` と mixed activation の統計を記録・表示します。

## 値と判定

値の内容は parse せず、`getenv()` が null かどうかだけを確認します。

| 値 | 判定 | 動作 |
|---|---|---|
| 未設定 | null | debug 出力・SYCL の debug buffer 割当てを行わない |
| 空文字 | non-null | 設定済みとして扱う |
| `0`、`false`、その他の文字列 | non-null | 設定済みとして扱う |

このため `STRATA_VERIFY_DEBUG=0` でも debug は有効です。大文字小文字、数値としての妥当性、先頭文字は関係しません。

## 有効になる条件

- CUDA と HIP の verifier は `src/core/verify.cpp` を使い、`g_dbg` が true のとき `VDBG` のログを出します。Metal ビルドでは `Verifier::run()` が Metal engine に委譲されるため、このファイル内の通常 verifier window の debug 行はその経路では実行されません。
- SYCL は `sycl/src/core/verify.cpp` に別実装があります。通常の `VDBG` 行は `g_dbg` に従います。
- SYCL の residual ladder と window 内容の詳細は、`STRATA_VERIFY_NO_HOST` が有効な経路でのみ出ます。`no_host` は同変数の未設定・空文字・`0` を無効、それ以外の非空文字列を有効と判定します。詳細ログの出力自体は各 window の実行後に `STRATA_VERIFY_DEBUG` の存在を再確認します。
- ソースはこの変数により verifier の計算方法や token 選択を変更していません。SYCL では診断のため device buffer の確保・コピー・統計計算が追加されるため、診断経路には実行時コストとメモリ使用があります。

## 実行時の詳細

CUDA/HIP と SYCL の `g_dbg` は翻訳単位の静的 bool で、プロセス起動時の環境を一度読みます。起動後に環境を変えても、これら `VDBG` ログの判定には反映されません。ログは `verify dbg: ` を付けて stderr に出し、各 `VDBG` 出力後に flush します。capture 完了、staging、launch、layer の開始・CPU expert 処理後、window 完了などが対象です。

SYCL では別に、Verifier 初期化時に `STRATA_VERIFY_DEBUG` が存在すると、各 layer の token 0 について `R` と mixed activation を記録する device buffer を確保します（各々 `n_layers * n_embd` 個の float）。`STRATA_VERIFY_NO_HOST` が有効で、かつ window 実行後にも `STRATA_VERIFY_DEBUG` が存在する場合、host sequence / skip、layer 0 の weights・IDs・residual、plan、各中間 tensor の統計、および layer ごとの `R` と mixed activation の平均絶対値・nonfinite 数を stderr に出します。layer 統計は `GDN` / `QSA` の区別も表示します。

SYCL のこの詳細出力は実行後に環境変数を直接再確認する一方、buffer の確保は初期化時です。そのため初期化後に環境を変更した場合、詳細ログが要求されても residual ladder 用 buffer は存在しない場合があります。反対に、初期化時だけ変数が設定されていると、詳細を出さなくても buffer が確保されます。

## ログと資料

ログ例の接頭辞は実装どおり `verify dbg: ` です。SYCL の `STRATA_VERIFY_NO_HOST` 下の詳細出力も `verify dbg:` を使います。これらは診断出力で、通常利用者向け設定の説明や性能保証ではありません。

`docs/INTEL.md` は、SYCL の `STRATA_VERIFY_DEBUG=1` が各 layer 後の `R` を表示する per-layer residual ladder として使われた、と記しています。同資料では streaming ring の調査で layer 5 からの NaN を見つける際に使ったと説明しています。現行ソースでは ladder buffer の記録と表示は `STRATA_VERIFY_NO_HOST` 経路に限られます。

## 根拠

- `src/core/verify.cpp:89,177,2235-2241,2252,2271,2295,2361-2374,2494`: CUDA/HIP の存在判定、ログ helper と利用箇所、Metal への委譲。
- `sycl/src/core/verify.cpp:70,77,765-771`: SYCL の静的 debug 判定、ログ helper、初期化時の buffer 確保。
- `sycl/src/core/verify.cpp:800-801,2183-2200`: `STRATA_VERIFY_NO_HOST` の parse と host handshake を省く条件。
- `sycl/src/core/verify.cpp:1524-1533,2309-2314,2331-2387`: layer ごとの値の記録、window timing、`no_host` 条件下の debug 表示。
- `docs/INTEL.md:264`: SYCL の residual ladder を使った調査例。
