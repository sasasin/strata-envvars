# `STRATA_GDN_TC_TILES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の GDN tensor-core split scan で、value head あたりの tile 数を 1 または 2 に選びます。設定値は tensor-core scan 全体を有効にするスイッチではありません。通常の非 split tensor-core scan が成功した場合、この値による tile 数の切り替えは使われません。実装は `gdn_tc_tiles()` とその呼び出し元 `gdn_recurrence_impl()` です（`engine/src/prefill/kernels.cu:1339-1355, 3198-3202, 3227-3237`）。

## 値と判定

`std::getenv` で値を取得し、`std::atoi` で整数化します。文字列全体の検証はなく、`atoi` が読む先頭の整数部分で判定します。未設定は `0`、空文字や数字で始まらない文字列も `atoi` が `0` を返すため自動選択です。変換後が正なら `1` は 1 tile、`2` 以上は 2 tiles に丸められます。変換後が 0 以下なら GPU の SM 数による自動選択です。したがって `1tail` は 1 tile、`2tail` や `99` は 2 tiles、`0`・`-1`・`true`・空文字は自動選択となります。先頭の空白や符号は `atoi` の規則で処理され、大文字小文字は判定対象になりません（`engine/src/prefill/kernels.cu:1340-1355`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA の split scan で環境値を参照 | 自動選択。SM 数が 96 以上なら 2、それ未満なら 1 | 整数化結果 `1` は 1 tile、`2` 以上は 2 tiles | 整数化結果 0 以下は自動選択（例: `0`, `-1`, `true`, 空文字） |
| GDN probe の override | 正の `tc_tiles` がなければ環境値を使う | probe 値 1 は 1 tile、2 以上は 2 tiles | 0 以下の probe 値は override にならず環境値へ進む |

## 有効になる条件

- CUDA の `gdn_recurrence_impl()` の経路で使われます。HIP ビルドではこの CUDA dispatch 区間はコンパイルされません（`engine/src/prefill/kernels.cu:3073-3080, 3177-3186`）。
- 自動 dispatch では、別途 `STRATA_GDN_TC` が `atoi` で 0 以外になり、token 数 `T >= 128` のときに tensor-core 経路を試します。これは別環境変数による条件であり、この文書の変数だけではその経路は有効になりません（`engine/src/prefill/kernels.cu:3186-3190, 3227-3237`）。
- まず通常の tensor-core scan を試し、成功した場合は終了するため tile 数の指定は適用されません。通常 scan が使えず split scan に進んだ場合に tile 数が渡されます（`engine/src/prefill/kernels.cu:3227-3237`）。
- split scan 自体にも GPU 条件があります。compute capability major が 8 以上、通常実行では 48 以上の SM、必要な shared memory が必要です。満たさない場合 `gdn_rec_tc()` はエラーを返します（`engine/src/prefill/kernels.cu:1365-1382`）。
- probe がある場合は `tc_tiles > 0` が環境値より優先します。probe はスレッド単位の試験・計測用フックで、通常 engine には probe がないとヘッダーに記載されています（`engine/include/strata/prefill/gdn_probe.hpp:3-10, 29-44`; `engine/src/prefill/kernels.cu:1340-1344`）。

## 実行時の詳細

通常の CUDA recurrence dispatch 節では `gdn_tc_tiles()` が呼ばれますが、その結果が tile 数として使われるのは split scan に進む場合です。probe の正の override がなければ関数内 `static const int` を初回評価時に一度だけ環境から読み、以後その値を使います。したがって環境値の初回読み取りは split scan の実行より前になる場合があり、実行中に環境値を変更してもキャッシュは再評価されません。自動選択時の SM 数も `sms_of[dev]` にデバイスごとにキャッシュされます（`engine/src/prefill/kernels.cu:1340-1355, 3198-3202`）。

split scan の `np == 3` かつ出力 norm を融合しない場合、2 tiles は `HV * 2` CTA の scan kernel、1 tile は `HV` CTA の scan kernel を起動します。正規化との融合が可能なときは 1 tile のみ融合用ポインタを渡し、2 tiles のときは後続の出力 norm kernel に任せます。2 tiles 以外の split variant（`np == 1` または `2`）は別の分岐で起動します（`engine/src/prefill/kernels.cu:1405-1423, 3198-3202, 3207-3208, 3234-3237, 3268-3269`）。

通常の自動実行で tensor-core scan と split scan が使えないときは、dispatch は後続の chunked 経路、さらに key-head / pipelined / columns 経路へ進みます。forced probe path では適格でなければ何も起動せず、`check("gdn_recurrence (forced path not eligible: nothing launched)")` を通します（`engine/src/prefill/kernels.cu:3239-3261`）。

## ログと測定値

この環境変数の読み取りや tile 選択自体に対応するログ出力はありません。最終的な `check("gdn_recurrence")` は CUDA エラーを検査し、エラー時は `exit_device_error("prefill gdn_recurrence", ...)` に渡します。理由ログと選択結果を記録する probe は試験用構造体の出力であり、通常 engine のログではありません（`engine/src/prefill/kernels.cu:110-116, 3259-3271`; `engine/include/strata/prefill/gdn_probe.hpp:35-39`）。

`docs/DETAILS.md` と `docs/GDN_CONTRACT.md` には親機能 `STRATA_GDN_TC` の説明がありますが、`STRATA_GDN_TC_TILES` 固有の測定値は確認できませんでした。そのため tile 数による性能差や数値結果は記載しません。

## 根拠

- `engine/src/prefill/kernels.cu:1339-1355` — 環境値の変換、1/2 への丸め、自動選択、SM 数キャッシュ。
- `engine/src/prefill/kernels.cu:1365-1382, 1405-1423` — split scan の適格条件と tile 数別 kernel launch。
- `engine/src/prefill/kernels.cu:3198-3237, 3239-3271` — norm 融合、通常/split scan の dispatch、fallback、エラー検査。
- `engine/include/strata/prefill/gdn_probe.hpp:3-10, 29-44` — probe override と probe の用途。
- `docs/DETAILS.md:1795-1803`, `docs/GDN_CONTRACT.md:62-70` — 親機能の説明との照合。対象環境変数固有の仕様・測定値は確認できない。
