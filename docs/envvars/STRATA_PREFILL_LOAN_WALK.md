# `STRATA_PREFILL_LOAN_WALK`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

prompt 処理用バッファを expert cache から借りるとき、貸出サイズを丸め済み chunk ではなく、その prompt piece が実際に通る walk に合わせて決める設定です。デフォルトで有効です。piece の token 数が walk floor 未満でも、256-token 単位に切り上げた chunk が floor 以上になる場合、貸出用 chunk を `floor - 1` にします。これにより staged walk の piece に streamed walk 用レイアウトを貸すことを避けます。環境変数は walk 自体を選びません。走査方式は別途 token 数と floor から決まり、この変数は貸出バッファの大きさだけを変えます（`src/program/generate.cpp:10436-10451`、`include/strata/prefill/loan_rules.hpp:20-25`、`src/prefill/prefill.cpp:4388-4392`）。

この判定は通常の `generate` prompt の cache 貸出サイズ決定と server の prompt segment 貸出の両方で使われます（`src/program/generate.cpp:10449-10451`、`src/program/generate.cpp:18372-18414`、`src/program/generate.cpp:21605-21637`）。実際の walk は prefill 側で `T >= stream_all_min()` と ring/source 条件を見て選びます。cache 貸出を行わない経路では、この設定による貸出サイズ変更はありません（`src/prefill/prefill.cpp:4390`）。

## 値と判定

`generate.cpp` の関数内 `static const bool` 初期化で `std::getenv` を一度呼び、値が存在していて先頭文字が `'0'` の場合だけ無効、それ以外は有効とします。文字列全体や数値としての妥当性は検査しません。未設定と空文字は有効です。初回の初期化後、同一プロセス内で環境を書き換えても反映されません（`src/program/generate.cpp:10441`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| この判定に到達する実行経路 | 有効（既定） | `1`、`true`、空文字、`0anything`、` 0` など、先頭が `0` でない値 | `0`、`0anything` など、先頭が `0` の値 |

無効値のときは貸出 chunk に選択済みの chunk をそのまま使います。有効値のときも、`walk_chunk` は `tokens > 0`、`chunk > 0`、`tokens < floor`、`chunk >= floor` の全条件が成立した場合だけ `floor - 1` を返し、それ以外は chunk を変更しません。したがって token 数が floor と等しい場合、丸め後 chunk が floor 未満の場合、または piece が floor 以上の場合は差がありません（`include/strata/prefill/loan_rules.hpp:20-25`）。

## 有効になる条件

- プロセスが `generate.cpp` の該当初期化と prompt chunk 選択に到達する必要があります。ここに OS/backend 別の条件分岐はありません（`src/program/generate.cpp:10441-10451`）。
- `STRATA_PREFILL_FUSED && !STRATA_PREFILL_MMQ` の build と、それ以外の build とで基準 chunk の選択実装は分かれますが、どちらの枝も同じ `loan_chunk` を利用します。環境変数の読み取り自体はこの macro 分岐より前です（`src/program/generate.cpp:10441-10451`、`src/program/generate.cpp:10453-10471`、`src/program/generate.cpp:10498`、`src/program/generate.cpp:18378-18407`、`src/program/generate.cpp:21605-21631`）。
- 実際の差が出るには、piece が正の token 数で floor 未満、選択された正の chunk が floor 以上であり、さらに prompt path が cache slot を借りる必要があります。server では `pf_parts.empty()` なら貸出処理を終えます（`src/program/generate.cpp:18372-18382`）。通常の generate では `--no-prefill-borrow` が指定されていないこと、host resource があり device resource もあることが借用開始条件です（`src/program/generate.cpp:21569-21574`）。
- floor は `Prefill::stream_all_min_tokens()` の値です。`STRATA_PREFILL_STREAM_MIN` が `atoll` で 0 以上に変換されるとその値が floor になり、負値または unset では build/backend、GPU・model 状態、および CPU share 等を使う既定計算に進みます。そのため floor が 0 以下なら正の token 数の piece はこの環境変数の貸出調整条件を満たしません（`src/prefill/prefill.cpp:614-624`）。
- 選択 chunk は `--prefill` / `--prefill auto`、host-aware plan、build 時の chunk 選択規則などで変わり得ます。この変数はそれらが選んだ chunk を受け取り、その後で貸出サイズを補正します（`src/program/generate.cpp:10429-10451`、`src/program/generate.cpp:18378-18414`、`src/program/generate.cpp:21605-21637`）。
- `STRATA_PREFILL_EQUAL` 等で chunk 選択が変わっても、貸出補正の規則自体は同じです。`STRATA_PREFILL_STREAM_MIN` は floor に作用するため、この設定が有効でも貸出補正の発生範囲を変えます（`src/program/generate.cpp:10460-10498`、`src/prefill/prefill.cpp:614-624`）。

## 実行時の詳細

`request_chunk` は正の token 数を最大 chunk 以下に制限し、256-token 境界へ切り上げた chunk を返します（`src/program/generate.cpp:10429-10435`）。その値を `loan_chunk(tokens, chunk)` が受け取り、設定が有効なら `walk_chunk(tokens, chunk, stream_all_min_tokens())` を呼びます。piece が floor 未満なのに切り上げ済み chunk が floor 以上となる場合だけ floor の直前まで貸出レイアウトを縮めます（`src/program/generate.cpp:10449-10451`、`include/strata/prefill/loan_rules.hpp:20-25`）。

Server では prompt segment ごとの `want_full` 等、通常の generate では `request_sized` 等の貸出サイズに補正値を使い、slot 数へ換算して cache から借りるか決めます。必要 slot 数が貸出上限に収まらなければ、既存の chunk 縮小または自前 buffer 経路が適用されます（`src/program/generate.cpp:18378-18414`、`src/program/generate.cpp:18444-18480`、`src/program/generate.cpp:21608-21643`）。

環境値は初回の `loan_by_walk` static 初期化で読み、その値をプロセス内で cache します。request ごとの再読込ではありません（`src/program/generate.cpp:10441`）。

## ログと測定値

この環境変数専用の有効・無効ログや警告はありません。通常の generate では貸出が成立すると `strata generate: prompt path borrows ... cache slots ...`、借りない場合は `strata generate: prompt path allocates its own buffers (no cache slots to borrow)` が stderr に出る箇所がありますが、値の判定や変更量は表示しません（`src/program/generate.cpp:21666-21674`）。Strata のコードコメントには特定条件の性能測定値がありますが、本変数の一般的な速度効果を示す測定としては扱いません。

## 根拠

- `src/program/generate.cpp:10429-10451` — chunk 丸め、環境変数の読み取り、貸出用 chunk の計算。
- `src/program/generate.cpp:18368-18414` — server の segment 貸出。
- `src/program/generate.cpp:18444-18480`、`src/program/generate.cpp:21605-21643` — cache slot に応じた通常の generate/server の貸出調整。
- `include/strata/prefill/loan_rules.hpp:20-25` — 有効条件と floor 直前へ縮める規則。
- `src/prefill/prefill.cpp:614-624`、`src/prefill/prefill.cpp:4389-4390` — walk floor の計算と streamed walk の条件。
