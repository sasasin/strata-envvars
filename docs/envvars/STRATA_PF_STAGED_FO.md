# `STRATA_PF_STAGED_FO`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

プロンプト処理の staged walk で、MMQ タイルのない fused-only 層についても、ルーティングされた expert を fused kernels の batched group entry (`fz_staged`) で処理するかを切り替える研究用スイッチです。通常この対象層は staged walk で dequantize-to-FP16 経路になります。entry が使われれば、その層の routed experts は entry の fused kernels に渡されます。変数は生成 token の選択や層の fused 対応形式そのものを変更しません。実際の対象層・実行条件は下記の条件にも従います（`src/prefill/prefill.cpp:408-427,5951-5965`、`include/strata/prefill/staged_fo_rule.hpp:1-10,45-47`）。

同じ判定は、`STRATA_PREFILL_STREAM_MIN` が未設定または負値で floor の自動決定に進む場合に、特定の Windows gfx1151 構成で long-prompt floor にも影響します。また、該当クラスでサーバーの `--short-read` が指定されていないとき、その既定値の選択にも使われます（`src/prefill/prefill.cpp:558-596,614-624,3406-3412`、`src/program/generate.cpp:1101-1102,3917,12919-12920`）。

## 値と判定

`staged_fo_on()` が `std::getenv` で値を読み、helper は文字列全体が厳密に `"1"` か `"0"` かを比較します。数値変換はせず、空白除去・大文字小文字変換もありません。`"1"` だけが明示的な on、`"0"` だけが明示的な off です。それ以外の設定値は未設定と同じく class default へ進みます（`src/prefill/prefill.cpp:412-426`、`include/strata/prefill/staged_fo_rule.hpp:15-29`）。

| 条件 | unset | 有効になる値 | 明示的に無効になる値／default 扱いの例 |
|---|---|---|---|
| native expert layout がロード済み | build・クラス・層構成と entry prerequisites から得る class default | `1` | `0`。`true`、`01`、`1 `、空文字、その他の文字列は default に戻る |
| layout が native でない、または format 一覧が空 | entry 判定は off | `1` | `0`。それ以外は off（この経路は class default を使わない） |

明示値と class default の評価は分けてください。ロード済み layout では `"1"` / `"0"` がそれぞれ判定結果を指定します。それ以外は class default です。no-MMQ build (`STRATA_PF_OWN_ONLY`) では全 device class が既定候補ですが、entry prerequisites が必要です。MMQ build では既定候補は Windows gfx1151 の測定クラスかつ全層が fused-only の場合に限られ、同じく prerequisites を要します（`src/prefill/prefill.cpp:409-425`、`include/strata/prefill/staged_fo_rule.hpp:20-29`）。

## 有効になる条件

- 実際の entry は prompt chunk が `stream_all_min()` 未満の staged walk に限られます。floor 以上は streamed walk となり、この entry を使いません（`src/prefill/prefill.cpp:4390,5958-5960`）。
- 対象層は fused kernels が形式をサポートし、MMQ tile がない fused-only 層である必要があります。`staged_entry_layer` は fused-only 層では `fo_on` を要求します（`include/strata/prefill/staged_fo_rule.hpp:45-47`）。
- `fz_staged` には native layout、当該層が通常 fused / WMMA / Hadamard-folded 経路でないこと、CPU share がその層の experts を取らないこと、peer がないこと、`m.pp` が false、group scratch cap が 0、weight-stationary mode が off、適用時の tail 対応、direct MMQ cache 条件を満たすことが必要です。さらに `STRATA_PREFILL_GROUP_GATHER` の判定が on、staged group entry が on、group size が両上限以下、nibble build では nibble layer でないことが必要です。どれかが不足すると `fz_staged` は選ばれず、この変数だけでは entry を強制しません（`src/prefill/prefill.cpp:5951-5965`）。
- staged group entry は CUDA build で既定 on、HIP build では `STRATA_PF_FUSED` が未設定または空文字でない場合に先頭文字が `1` なら on です（`STRATA_PF_FUSED=1` が案内される opt-in 値です）。`STRATA_PREFILL_GROUP_GATHER` は未設定または `atoi(value) != 0` のとき on です（`src/prefill/prefill.cpp:307-327`、`include/strata/prefill/staged_group_rule.hpp:12-15`）。
- class default の device 判定は Windows HIP のみで行われ、GPU が 1 枚見え、その device が gfx1151 のとき測定クラスです。別 OS/backend/device はこのクラス判定を満たしません。MMQ build ではさらに全層が fused-only である必要があります。`STRATA_PREFILL_MMQ` が設定され `atoi(value) == 0` の場合、`layers_all_fused_only()` は false となり、MMQ build のこの class default 条件を満たしません（`src/prefill/prefill.cpp:373-386,388-406,425`）。
- build macro `STRATA_PF_OWN_ONLY` は「MMQ なし」の class default を全 device class に広げます。ただし `fz_staged` 自体の prerequisites と各層の fused 対応条件は引き続き必要です（`src/prefill/prefill.cpp:420-425,5958-5965`）。
- floor に対する効果は、他の条件で `stream_floor_default()` が floor を決める場合に限られます。Windows gfx1151・全層 fused-only で entry off の場合、既定 floor は 64 tokens になります。entry on ならこの条件による 64 への引き下げはなく、通常の既定 1,024 が残ります（ただし別の floor 規則もあります）。`STRATA_PREFILL_STREAM_MIN` が `atoll` 後 0 以上ならその値が floor を上書きします。設定値が負なら自動決定へ進みます（`src/prefill/prefill.cpp:558-567,614-624`、`include/strata/prefill/stream_floor_rule.hpp:20-21,45-49`）。
- `--serve` で `--short-read` が明示されると、その値が `short_read_default()` の結果より優先されます。未指定時も、この環境変数による既定変更は native layout、Windows gfx1151、全層 fused-only などの条件が揃う場合に限られ、Hadamard-folded trellis の例外があります（`src/program/generate.cpp:1101-1102,3917,12919-12920`、`src/prefill/prefill.cpp:3407-3412`、`include/strata/prefill/staged_fo_rule.hpp:32-42`）。

## 実行時の詳細

`staged_fo_on()` は layout が未ロード（native でない、または format 一覧が空）の呼び出しでは、環境値をその場で評価し、その結果を cache しません。layout がある場合は `STRATA_PF_STAGED_FO` を読み、default を含む結果を atomic static cache に保存します。その後の呼び出しは cache を返すため、cache 後にプロセス環境を変更しても判定は変わりません。layout の読み込み前に行った呼び出しは cache されないため、後の呼び出しで再評価されます（`src/prefill/prefill.cpp:412-427`）。

entry が選ばれた層では、routed expert の bounds を構築し、token activation を native int8 表現に量子化してから、staged / resident expert を batch にまとめて `fused::experts_native` に渡します。entry は routed experts のみを対象とします（`src/prefill/prefill.cpp:6028-6040,6073-6097,6697-6719,6990-6993`）。

この判定は `--serve` の `--short-read` 既定値にも呼び出されます。該当する class・layout 条件で `--short-read` が未指定なら、基底の 64 から staged entry と verify windows の測定上の交点である 24 に変わります。CLI 指定があると class default の問い合わせ自体を行いません（`src/prefill/prefill.cpp:3406-3412`、`include/strata/prefill/staged_fo_rule.hpp:32-42`、`src/program/generate.cpp:3917,12919-12920`）。

## ログと測定値

MMQ build で fused-only 層が初めて `fz_staged` を通ると、stderr に次の文言を一度出します（`src/prefill/prefill.cpp:6028-6038`）。

```text
strata prefill: a layer with no MMQ tile reads prompt pieces below %lld tokens on the fused kernels' staged group entry, routed experts only. STRATA_PF_STAGED_FO=0 keeps the old rule.
```

`%lld` は実行時の `stream_all_min()` です。`STRATA_PF_OWN_ONLY` build ではこのログ部分は compile-time で除外され、build の起動行を `own_only_line_flush()` が出す経路です（`src/prefill/prefill.cpp:6030-6036,626-635`）。この環境変数固有の無効値警告やエラー文言は実装にありません。ここでは実測値を新たに主張しません。

## 根拠

- 直接の環境読み取りと cache: `src/prefill/prefill.cpp:412-427`
- 値比較と class default 判定: `include/strata/prefill/staged_fo_rule.hpp:15-29`
- entry の条件と処理: `src/prefill/prefill.cpp:5951-5965,6028-6040,6697-6719`
- floor と `STRATA_PREFILL_STREAM_MIN`: `src/prefill/prefill.cpp:558-596,614-624`、`include/strata/prefill/stream_floor_rule.hpp:20-49`
- `--short-read` との関係: `src/prefill/prefill.cpp:3406-3412`、`src/program/generate.cpp:1101-1102,3917,12919-12920`
- 一覧との照合: `docs/SETTINGS.md:342` は NVIDIA / AMD の on/off スイッチとして掲載していますが、実装上の unset default は build macro・OS/device class・layer layout・entry prerequisites によって異なります。索引 `docs/envvars/000_envvers.md:1693` は候補名として掲載しており、直接読み取りは `src/prefill/prefill.cpp:416` で確認しました。
