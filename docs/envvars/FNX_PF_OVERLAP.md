# `FNX_PF_OVERLAP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

split engine の prompt prefill で、各 chunk の attention/FFN sum を専用 `ring_st` stream で実行し、その間に pass 内の次 chunk の計算を進める経路を選びます。未設定時は有効です。この設定は通常の Strata engine 全体ではなく、`src/split/src/prefill.cu` の split engine の prefill state に適用されます。split engine は CUDA/HIP 用の `strata-split-*` 実行ファイルとして構成されています（`src/split/CMakeLists.txt:92-120`）。

## 値と判定

共通 helper `env_int` が値全体を符号付き base-10 `long long` として読み、`p->overlap` はその値が 0 以外かを判定します。値の有無ではなく数値で判定し、空白や末尾文字を許しません。

| 値 | 判定 |
|---|---|
| unset | 既定値 `1`。ただし `FNX_PF_RING_SM` が 0 以外なら短絡評価でこの変数は読まれず、overlap は無効 |
| `0`, `-0`, `+0` | 無効 |
| 0 以外の有効な整数（負値を含む） | 有効 |
| 空文字、空白、`true`、`1x`、整数範囲外 | `env_int` が `FNX_PF_OVERLAP: '<値>' is not a whole number` の例外を投げる |

`parse_whole` は先頭文字が符号または数字であることを確認した後 `strtoll(..., 10)` を使い、変換末尾が NUL であることと `ERANGE` でないことを要求します。設定値に対する追加の範囲制限や clamp はありません。CLI 引数による上書きはありません。`FNX_PF_RING_SM` が有効な場合はそちらの経路が優先され、overlap は無効になります（`src/split/src/env.hpp:15-22,33-40`; `src/split/src/prefill.cu:738-745,821`）。

## 有効になる条件

- `Engine::prefill_alloc()` が実行される split engine で使われます。同関数は model の各 card に対して prefill state を作ります。通常 engine の設定ではありません（`src/split/src/engine.cu:274-275`; `src/split/src/prefill.cu:625-635,821-830`）。
- `FNX_PF_RING_SM` が 0 のときに限り、この変数を読み取って有効/無効を決めます。`FNX_PF_RING_SM` が 0 以外なら GPU-thread ring 経路となり、`FNX_PF_OVERLAP` の値にかかわらず `p->overlap` は false です（`src/split/src/prefill.cu:738-745,821`）。
- 有効時は専用 non-blocking `ring_st` stream と、各 pass slot の `ev_go` / `ev_ra` / `ev_rf` event を作成します。stream/event 作成に失敗すれば `ckc` が例外経路へ進みます（`src/split/src/prefill.cu:822-830`）。
- `p->overlap` は pass 中の chunk 処理で参照されます。次 chunk の計算と並行できるのは、同じ pass に後続 chunk がある場合です。単一 chunk の pass に overlap の並行対象はありません（`src/split/src/prefill.cu:990-1015,1151-1163`）。

## 実行時の詳細

各カードの `Pf` を割り当てる初期化中に値を読み、bool `p->overlap` に保持します。`static` cache はありませんが、prefill state 作成後の環境変更を再読するコードもありません。新しい Engine を作ればその初期化時点の環境値が使われます（`src/split/src/prefill.cu:625-635,821`）。

overlap 時、半分の出力と必要な routed-expert addend が準備できると、main stream で `ev_go` を記録します。`ring_st` はその event を待ち、`pf_ring` を実行した後に attention sum 完了の `ev_ra` または FFN sum 完了の `ev_rf` を記録します。次の chunk を計算している間に sum を進め、次の half へ移る箇所では対応する event を待ちます。attention merge も、次 chunk の HC read が発行されるまで保留されます。該当箇所は `src/split/src/prefill.cu:1151-1172,1182,1232-1255,1299-1306` です。

`FNX_PF_RING_SM=0` かつ `FNX_PF_OVERLAP=0` の場合は専用 stream/event を作らず、attention と FFN の sum を main stream 上の `pf_ring` で実行します（`src/split/src/prefill.cu:1241-1247,1299-1306`）。この変数専用の ON/OFF ログはありません。`FNX_PF_TIMING` が有効なら pass の所要時間などが stderr に出ますが、それ自体は overlap の有効状態を示しません（`src/split/src/prefill.cu:1353-1364`）。

無効な文字列を初期化時に読むと例外になります。sFNX は起動時の例外を stderr の `sfnx: failed: ...` と標準出力の `ERR ...` に出して終了コード 1 で終了し、`fnx_run` は stderr に `fnx_run: ...` を出して終了コード 1 を返します（`src/split/tools/sfnx.cpp:1027-1035,1050-1055`; `src/split/tools/fnx_run.cpp:1364-1373`）。実行中の prefill では ring error があれば `prefill: ring error <値>`、pass が 120 秒以内に完了しなければ `prefill: a pass did not finish in 120 s (a ring step's flag never came?)` の例外になります。これらは ring 実行の一般的な失敗経路であり、この環境変数固有の警告ではありません（`src/split/src/prefill.cu:1320-1335`）。

## 根拠

- 候補名を含む実コード参照は `src/split/src/prefill.cu:821` の `env_int("FNX_PF_OVERLAP", 1)` です。ほかの完全一致参照は同ファイルのコメント `:384,1151` で、追加の読取箇所ではありません。
- helper の定義と parse: `src/split/src/env.hpp:15-22,33-40`。
- overlap state と処理: `src/split/src/prefill.cu:351-388,821-830,1151-1163,1173-1255,1299-1306`。
- 文書 `docs/SPLIT_ENGINE.md:68-77` は split prompt の copy-engine ring と `FNX_PF_RING_SM=1` の GPU-thread ring、および両者の回答差の資料を説明していますが、`FNX_PF_OVERLAP` の性能測定値は示していません。本調査では性能向上率や生成結果への影響を断定していません。
