# `STRATA_ADAPT_ASYNC_WAIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP 実装の適応型 expert tier が arena から GPU cache へ expert をコピーインするとき、非同期コピーの完了をその場で待つか、完了を polling しながら次の tick まで戻るかを決めます。unset 時は待つ設定です。これは非同期 tier 自体を有効にするスイッチではなく、コピー完了の待ち方だけを選びます。値は `generate.cpp` の tier 初期化時に一度 `a_wait` へ読み込まれ、`SwapIn` 状態の完了判定に使われます（`engine/src/program/generate.cpp:15491-15502, 15660-15670, 15778-15781`）。

arena では適応 round が GPU cache の resident 状態を更新する前にコピーインの完了を確認します。待つ設定ではコピー完了まで `ajob->wait()` と `cudaEventSynchronize()` を行い、待たない設定では `ajob->idle()` と `cudaEventQuery()` で確認し、未完了ならその tick は戻ります。したがって値が変えるのは新しい expert を resident として反映するタイミングです。swap 候補の選択基準そのものは変えません。ソースコメントも、待つ設定では expert が最初に GPU で実行される window が timing に依存しないと説明していますが、適応 tier 全体については run 間で bit-exact ではないと記しています（`engine/src/program/generate.cpp:15437-15439, 15460-15472, 15660-15670, 15778-15789`）。

## 値と判定

`a_env(name, def)` が `std::getenv` で取得し、未設定または空文字列なら既定値を返し、それ以外は `std::atoi` の戻り値を使います。`STRATA_ADAPT_ASYNC_WAIT` の既定値は `1`、有効判定は変換値が 0 以外です。文字列全体の検証、真偽語の比較、範囲 clamp はありません（`engine/src/program/generate.cpp:15494-15502`）。

| 条件 | unset | 待つ設定になる値の例 | polling になる値の例 |
|---|---|---|---|
| arena で非同期 tier が動作中 | `1`（待つ） | `1`, `2`, `-1`, `1tail`, ` 1`（`atoi` が非 0） | `0`, `0tail`, 空白だけ, `true`, `false`（`atoi` が 0） |
| arena 以外、または非同期 tier が動作していない | `a_wait` は偽、または値を使う `ajob` がない | 実効しない | 実効しない |

`atoi` は数値全体が有効か検査しないため、先頭の整数部分を読める文字列では後続文字を無視します。大文字小文字を含む `true` / `false` の意味づけはなく、どちらも数値変換結果 0 です。空文字だけは `atoi` に渡さず既定値に戻ります。変換値に対する clamp や追加の無効値 fallback はありません（`engine/src/program/generate.cpp:15494-15502`）。

この変数を上書きする CLI 引数や別の環境変数はありません。`--adapt-async` と別変数 `STRATA_ADAPT_ASYNC` は非同期 tier の起動選択を制御します。たとえば `--adapt-async 0` は tier を使わない指定であり、`STRATA_ADAPT_ASYNC_WAIT=0` の polling 指定とは別です。`--adapt-async 1` が適用条件を満たして tier を有効にすれば、`STRATA_ADAPT_ASYNC_WAIT` はその待ち方を決めます（`engine/src/program/generate.cpp:4056, 11691-11732`、`engine/include/strata/core/adapt_async_default.hpp:35-60`）。

## 有効になる条件

- 実読み取りは CUDA/HIP 側の `engine/src/program/generate.cpp` にあります。SYCL 側の別実装 `engine/sycl/src/program/generate.cpp` にはこの名前の読み取りがありません（全参照検索結果。GPU executable のソース登録は `engine/cmake/strata_gpu_engine.cmake:548-551`）。
- `srcp == &arena_src` のときだけ `a_env("STRATA_ADAPT_ASYNC_WAIT", 1)` が評価されます。resident RAM mode でも arena 以外なら `a_wait` は偽で、この設定による待ち方の変更はありません（`engine/src/program/generate.cpp:15491-15502`）。
- 実際に待ち方が使われるには非同期 tier の job thread (`ajob`) が必要です。明示的な `--adapt-async 1` は `--serve`、適応 tier が有効（`--adapt-every` と `--adapt-swaps` が正）、arena の場合は layer split と `--pipeline-windows 2` なし、さらに `--batch-groups`、peer device、remote expert optimization 等の制約を満たす必要があります。条件を満たさない場合は理由付きで `--adapt-async 1` が無効化されます（`engine/src/program/generate.cpp:11691-11732`）。
- 明示的な `--adapt-async` がない場合、測定による自動選択は CUDA build、`--serve`、適応 tier 有効、arena、単一 GPU、pipeline windows なし、batch slots なし、peer/remote expert なし、`STRATA_ADAPT_OVERLAP` なし、`STRATA_ADAPT_FETCH` が 0 相当、かつ `STRATA_ADAPT_ASYNC` が 0 相当でない場合に限られます。HIP build ではこの自動選択をしません（`engine/include/strata/core/adapt_async_default.hpp:19-60`、`engine/src/program/generate.cpp:11695-11715`）。
- Windows HIP で明示的に非同期 tier を要求した場合は、別設定 `STRATA_WIN_HIP_RISKY` による guard が先に働き、拒否される場合があります（`engine/src/program/generate.cpp:11682-11689`）。
- これらの tier 条件を満たしても、その round に移動候補がなければコピー完了待ちは発生しません。コピー batch を複数 tick に分けるかどうかは別変数 `STRATA_ADAPT_ASYNC_BATCH` が決めます（`engine/src/program/generate.cpp:15502, 15537-15571, 15756-15760, 15778-15794`）。

## 実行時の詳細

値は適応 tier の状態を組み立てるときに `const bool a_wait` として読みます。関数内で環境変数を再読せず、static cache でもありません。現在の tier 実行中に環境値を変更しても `a_wait` には反映されません（`engine/src/program/generate.cpp:15491-15502`）。

arena では各 round のコピーイン後、`SwapIn` で `a_ready(drain || a_wait)` を呼びます。`a_wait` が真なら job と各 GPU event の完了を同期的に待ち、完了後に resident table の incoming expert を新しい slot に割り当てます。`a_wait` が偽なら job が idle でない場合、または event が `cudaErrorNotReady` の場合に未完了として戻り、後続 tick で再確認します。いずれも完了を確認した後で resident table を更新し、arena の source を release します（`engine/src/program/generate.cpp:15660-15670, 15778-15789`）。

ただし `drain` 中は `drain || a_wait` が真になるため、値が 0 でも request 境界や quiesce で in-flight round を片付ける経路は待ちます。polling 設定は通常 tick のコピー完了判定を変えるもので、slot を安全に貸し出す前の drain を省きません（`engine/src/program/generate.cpp:15778-15781, 15829-15839, 21305`）。

## ログと測定値

変数を読んだ時点での専用警告やエラーはありません。arena の非同期 tier が動作して request の集計行が出る場合、stderr に `strata serve: asynchronous adaptive tier: ...` に続いて ` (arena, copy-in only, batch %zu, wait %d, pick %s %.2f ms/round)` と出力され、`wait` が `a_wait` の 0/1 を示します（`engine/src/program/generate.cpp:23704-23713`）。自動選択が測定後に非同期を試す場合は、`strata serve: adaptive tier: the swaps held the windows up ... trying the asynchronous tier for a while` 等の行が出ますが、これは `STRATA_ADAPT_ASYNC_WAIT` 固有のログではありません（`engine/src/program/generate.cpp:23057-23076`）。

コピー API の失敗は `strata serve: adaptive tier: copy of layer ... failed: ...` 等を stderr に出します。GPU event の同期・query 失敗は `a_err` に記録され、通常 tick では stdout に `ERR an adaptive refill failed` を出して serve を終了コード 1 で終えます（`engine/src/program/generate.cpp:15660-15670, 15615-15624, 22852-22855`）。

`docs/DETAILS.md:1651` は RTX 3090 + Ryzen 5 5600X の `--adapt-async 1` による decode 結果を挙げていますが、WAIT の値ごとの比較とは記していません。対応する community report も blocking と `--adapt-async 1` を比較した測定で、WAIT の効果を分離していません（`docs/bench-results/2026-10-11-community-rtx3090-5600x-arena-async/README.md:5-16, 18-39`）。同 report の harness には `STRATA_ADAPT_ASYNC_WAIT=0` を指定する `async_nowait` arm がありますが、README にその arm の結果は掲載されていません（`docs/bench-results/2026-10-11-community-rtx3090-5600x-arena-async/strata_ab2.py:40-46`）。したがって WAIT 固有の速度・正確性測定値はここでは示しません。

## 根拠

- 全参照検索: Strata checkout で名前の実参照は `engine/src/program/generate.cpp:15501`。同ファイルの他の出現はコメント、ほかの出現はベンチ harness と terminal settings register。
- 読み取り・既定値・判定: `engine/src/program/generate.cpp:15491-15502`
- コピー完了の待機と polling: `engine/src/program/generate.cpp:15660-15670, 15778-15789`
- 明示・自動の非同期 tier 条件: `engine/src/program/generate.cpp:11682-11732`, `engine/include/strata/core/adapt_async_default.hpp:19-60`
- 観測可能な tier 統計: `engine/src/program/generate.cpp:23704-23713`
