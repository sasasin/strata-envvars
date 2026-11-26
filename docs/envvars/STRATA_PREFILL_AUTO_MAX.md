# `STRATA_PREFILL_AUTO_MAX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--prefill auto` が選べる prompt chunk の上限を、既定の 8192 から 16384 または 32768 token に引き上げます。値は上限であり、実際にその大きさの chunk が使われる保証ではありません。コンテキスト長、expert cache から借りられる領域、host RAM などに応じて実行時 planner が小さい値を選びます。通常の token 逐次処理や生成 token の選択を直接指定する変数ではありません。共通 engine と SYCL engine の `--prefill` 引数解析で読み取られます。`--prefill` 自体は `--native` を必要とします（`engine/src/program/generate.cpp:1377-1379`、`engine/sycl/src/program/generate.cpp:940-942`）。

## 値と判定

両 engine は `--prefill` を解析するたびに `std::getenv` で読み、`--prefill auto:N` の `N` がない場合に限り、auto かつ環境変数が設定済みなら `std::atoll` の結果を上限へ変換します。変換後は、32768 以上なら 32768、16384 以上なら 16384、それ未満なら 8192 です。数値全体の検証やエラー処理はありません（`engine/src/program/generate.cpp:4000-4008`、`engine/sycl/src/program/generate.cpp:2018-2027`）。

| `STRATA_PREFILL_AUTO_MAX` の状態 | `--prefill auto` で得る上限 | 例 |
|---|---:|---|
| 未設定 | 8192 | 環境変数による引き上げなし |
| 空文字、数値として 16384 未満、数値で始まらない文字列 | 8192 | `""`, `0`, `1`, `16383`, `-1`, `true`, `false`, `abc` |
| `std::atoll` が 16384 以上 32768 未満を読む文字列 | 16384 | `16384`, `20000`, `16384tail` |
| `std::atoll` が 32768 以上を読む文字列 | 32768 | `32768`, `65536` |

`atoll` は先頭の空白や符号を許し、数値の後ろに続く文字を検証しません。従って `  +16384tail` は 16384 として扱われます。大文字小文字の区別は値の判定に関係しません。範囲外整数の変換結果はコードで検査されていません。空文字や不正な文字列は parse error にならず、変換結果 0 から 8192 になります。

`--prefill auto:N` は環境変数より優先され、`N` を同じ 8192 / 16384 / 32768 の段階へ丸めます。`--prefill N` の数値指定には環境変数は適用されません。`--prefill auto:N` の `N` も `atoll` で読み、同じ閾値で丸められます（`engine/src/program/generate.cpp:4000-4008`、`engine/sycl/src/program/generate.cpp:2018-2027`）。

## 有効になる条件

- `--prefill auto` または `--prefill auto:N` が必要です。変数だけ設定して `--prefill` を指定しない場合、parser はこの変数を読みません。複数回 `--prefill` がある場合、引数解析で後に処理された値が option state を更新します（`engine/src/program/generate.cpp:4000-4008`）。
- 実際の prompt chunking が行われるには `--native` と、複数 token の prompt が必要です。prompt 処理は `prefill_chunk > 0 && n_prompt > 1` の場合に入ります（`engine/src/program/generate.cpp:1377-1379,23989-23996`、SYCL: `engine/sycl/src/program/generate.cpp:940-942,13311-13318`）。
- build 対応範囲は共通 engine（CUDA/HIP 系）と SYCL engine です。SYCL 側にも独立した読み取りがあります。Metal 用にこの変数を読む箇所は見つかりません（全参照確認: `engine/src/program/generate.cpp:4004`、`engine/sycl/src/program/generate.cpp:2022`）。
- 明示的な `--prefill auto:N` は、この環境変数より優先します。モデル context が上限より小さければ上限は context まで下がります（共通 engine: `engine/src/program/generate.cpp:11244-11248`、SYCL: `engine/sycl/src/program/generate.cpp:6679-6683`）。
- `--serve` でも同じ解析済み option が使われ、server の prompt chunk planner が cache ごとの貸出可能量で選び直します。SYCL server は結果を `strata serve: prompt chunk auto: ...` と出力します（`engine/sycl/src/program/generate.cpp:7297-7327,7385-7400`）。共通 engine の単一 GPU prompt 処理は選んだ値を `strata generate: prompt chunk auto: ...` と出力します（`engine/src/program/generate.cpp:23990-24004,24055-24070`）。
- 共通 HIP/CUDA engine では、環境変数が設定されていると bare `--prefill auto` として扱わないため、bare auto 専用の hardware default 規則も走りません。これは空文字や不正値でも同じです。従って Windows HIP の bare-auto 6144 cap、NVIDIA/GFX12/GFX11 の bare-auto ceiling 引き上げを使わず、変数から得た 8192/16384/32768 の上限になります。`--prefill auto:N` も同じく bare-auto 規則の対象外です（`engine/src/program/generate.cpp:4016-4019,4494-4595`）。
- cache lending の適合性、RAM guard、マルチ GPU layer split も実際の値を下げる場合があります。NVIDIA/GFX12/GFX11 の hardware default 規則が bare auto に設定した上限は、layer split で通常 8192 に戻ります（`STRATA_SPLIT_CHUNK16K=1` の場合を除く）。この分岐は環境変数が設定された auto には適用されません（`engine/src/program/generate.cpp:11248-11258`）。

## 実行時の詳細

環境変数は option parser が `--prefill` を処理する時に読み、その結果を `Options::prefill_auto_max` と `prefill_chunk` に保存します。リクエストごとにこの変数を再読する箇所や static cache はありません。プロセス起動後の環境変更は既に解析済みの option に反映されません。server では保存した上限を各 prompt の計画に使います（共通 engine: `engine/src/program/generate.cpp:4000-4008,11244-11248,23990-24004`、SYCL: `engine/sycl/src/program/generate.cpp:2018-2027,6679-6683,13311-13327`）。

共通 engine の auto planner は上限と context の小さい方を ceiling とし、expert cache の借用量や ring の予算に合う chunk を探します。GPU cache から prompt buffer を借りられない場合など、選択 chunk が上限を下回る経路があります。大きい bare-auto default ceiling を使う CUDA/HIP 規則では、追加の cache loan に対する host RAM が不足すると 32768 → 16384 → 8192 と段階的に上限を縮めます（`engine/src/program/generate.cpp:11248-11258,11260-11303,11334-11342`）。SYCL 側も context 上限と cache/ring 予算内で選択します（`engine/sycl/src/program/generate.cpp:6683-6689,6740-6754`）。

この変数自体について無効値を理由に終了する経路はありません。値は数値変換と段階化に使われ、範囲検証エラーは出ません。実行時に選ばれた chunk のログは `strata generate: prompt chunk auto: %lld tokens`（共通 engine）または `strata serve: prompt chunk auto: %lld tokens, a %lld-slot ring`（SYCL server）です（`engine/src/program/generate.cpp:24061-24064`、`engine/sycl/src/program/generate.cpp:7386-7396`）。

## ログと測定値

この環境変数の設定や parse だけを知らせるログはありません。共通 engine の platform 固有 bare-auto ceiling の案内ログ（例: `strata generate: gfx12: --prefill auto may take chunks up to ...`）は、この環境変数が未設定で bare-auto 規則が有効な場合のものです（`engine/src/program/generate.cpp:4494-4504,4537-4559`）。

`docs/DETAILS.md:1209` は gfx12 Linux の bare `--prefill auto` を説明し、明示した `STRATA_PREFILL_AUTO_MAX` はその既定規則で変更しないと記載しています。同資料の測定値は R9700 の IQ3_S prompt 20K +12%、32K +1.3%、64K +2.6%、UD-Q4_K_XL 20K +26% などですが、gfx12 の bare-auto default の比較値であり、この環境変数を個別に設定した測定ではありません。`docs/DETAILS.md:1513-1519` も CUDA の大きい chunk の測定を記していますが、ここでも本変数単独の測定値とは扱いません。

## 根拠

- `engine/src/program/generate.cpp:4000-4021` — 共通 engine の CLI 値、環境変数、bare-auto 判定。
- `engine/sycl/src/program/generate.cpp:2018-2027` — SYCL engine の同じ読み取りと変換。
- `engine/src/program/generate.cpp:4494-4595` — bare-auto 時にだけ適用される CUDA/HIP hardware 規則。
- `engine/src/program/generate.cpp:11244-11303,23989-24070` — 上限、RAM guard、実行時 chunk 選択とログ。
- `engine/sycl/src/program/generate.cpp:6679-6689,7297-7327,7385-7396,13311-13327` — SYCL 上限、cache planner、server/generate の chunk 結果。
- `engine/include/strata/platform/host_limits.hpp:22-30` — Windows HIP の bare-auto cap 判定。
