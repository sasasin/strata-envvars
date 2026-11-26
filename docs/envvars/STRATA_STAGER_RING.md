# `STRATA_STAGER_RING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prompt prefill の expert stager が、未 resident の expert blob をコピーしておく host buffer ring の深さを指定する。ring の各 slot は最大 blob サイズのバッファを持ち、コピー thread は DMA が終わった slot を再利用する。値を大きくすると同時に先行できるコピー数と確保する host buffer 数が増える。通常の CUDA/HIP 経路と SYCL 経路に読み取りがある。`Prefill::init` が stager を作るときの設定であり、CLI 引数による上書きは見つからなかった。`engine/src/prefill/prefill.cpp:1121-1129,1156-1162,1297-1305`、`engine/sycl/src/prefill/prefill.cpp:464-472,502-515,620-638`。

## 値と判定

両実装とも `std::getenv` で設定有無を見て、設定されていれば `std::atoi` の結果を `std::clamp(..., 2, 256)` に渡す。数値文字列全体の妥当性検査や文字列比較はない。`atoi` が読む数値の接頭部分が使われ、先頭空白や符号も `atoi` の規則で処理される。空文字や数値に変換できない文字列は 0 になり、下限の 2 になる。数値の後ろの文字は検査されず、たとえば `16junk` は 16、`0anything` は下限の 2 になる。範囲内の整数はそのまま、2 未満は 2、256 超は 256 に制限される。`atoi` の整数型範囲外入力の結果はコードで検査されない。`engine/src/prefill/prefill.cpp:1156-1158`、`engine/sycl/src/prefill/prefill.cpp:502-505`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・変換結果 |
|---|---|---|---|
| CUDA/HIP および SYCL の stager 初期化 | 通常は 16。`ExpertSource::transient` が true となる file-tier の expert があり、後述の profile 選択も files のままなら `4 * threads` | `2`〜`256`（例: `16`, `16junk`, ` 16` は 16） | `0`, `1`, `-3`, 空文字, `true`, `abc` はいずれも 2。`257` は 256 |

unset 時の `4 * threads` は、stager 初期値 16 を `init` より前に置き換える分岐による。通常 engine では `STRATA_STAGER_THREADS` が設定されていればその `atoi` 値を 1〜32 に制限した値が threads 数となる。未設定なら files profile で 32、通常 profile では hardware concurrency から 2〜4 を選ぶ。通常 engine で `files && !STRATA_STAGER_THREADS` の場合は `STRATA_STAGER_SSD` が非空なら先頭文字が `'0'` 以外で files profile を強制し、空または先頭 `'0'` なら無効にする。未設定または空なら `cached_share(256) >= 0.9` のとき files profile をやめる。SYCL は transient source なら files profile を選び、`STRATA_STAGER_THREADS` の有無でこの分岐自体を無効にはしない。明示的に `STRATA_STAGER_RING` が設定されると、この profile ごとの ring 既定値より `atoi` と clamp の結果が優先される。`engine/src/prefill/prefill.cpp:2523-2546`、`engine/sycl/src/prefill/prefill.cpp:1491-1503`。

## 有効になる条件

- Strata の CUDA/HIP または SYCL engine で prompt prefill の `Prefill::init` が stager を初期化すること。Metal 分岐は `Prefill::init` の冒頭で別経路へ return するため、この stager 設定は使わない。`engine/src/prefill/prefill.cpp:2443-2455`。
- ring の slot 数は stager 初期化時に配列・host buffer を確保する数となる。CUDA/HIP 側では各 slot に `MAXBLOB()` bytes の buffer を確保し、pinned allocation に失敗した slot は pageable buffer に fallback する。SYCL 側も同じ深さで host allocation を試し、失敗時は pageable buffer を使う。`engine/src/prefill/prefill.cpp:1156-1170`、`engine/sycl/src/prefill/prefill.cpp:502-535`。
- stager は `m.stager` がまだない場合にだけ作られる。file-tier source の有無は unset 時の自動 ring 値に影響するが、明示値を読む条件にはならない。`engine/src/prefill/prefill.cpp:2523-2555`、`engine/sycl/src/prefill/prefill.cpp:1491-1503`。
- `STRATA_STAGER_BATCH` は別設定で、CUDA/HIP 経路では job のまとめ数を 1〜32 に制限した後、ring 深さ以下にする。したがってリングを小さくすると batch の実効上限も小さくなる。SYCL の該当箇所では batch 設定を確認できなかった。`engine/src/prefill/prefill.cpp:2547-2555`。

## 実行時の詳細

値は `Stager::init` のたびに読み取られ、読み取った深さで `buf`, `pinned`, DMA event の配列と pageable fallback を初期化する。`Prefill::init` は `m.stager` が null のときだけ stager を作成し、その後の relayout や同じ `Prefill` インスタンス内の再利用では ring 値を読み直さない。したがって初期化後の環境変更は既存 stager に反映されない。プロセス起動時に一度だけ読む static cache ではなく、stager 初期化時の読み取りである。`engine/src/prefill/prefill.cpp:1156-1162,2523-2557`、`engine/sycl/src/prefill/prefill.cpp:502-515,1491-1505`。

worker は job `j` を buffer `j % kRing` にコピーする。以前の job の DMA が終わるまで同じ slot の再利用を待ち、launch thread はコピー完了後にその buffer から device への DMA を記録する。CUDA/HIP では同期 event を使い、SYCL では event / sequence 値を使う。よって ring 深さは host copy が DMA より先行できる幅と host buffer の個数を変える。これは prefill の expert staging 用であり、ソース上では routing や model parameter を選ぶ設定としては使われていない。`engine/src/prefill/prefill.cpp:1205-1248,1297-1305`、`engine/sycl/src/prefill/prefill.cpp:567-638`。

## ログと測定値

この変数専用の有効化・無効化ログはない。CUDA/HIP 経路で `STRATA_PF_ALLOC_TRACE` が設定されている場合は、初期化の `prefill alloc trace` 行に stager ring の確保要求量（`kRing * MAXBLOB()` bytes を MiB にした値）が出るが、ring の slot 数そのものを表示する行ではない。`engine/src/prefill/prefill.cpp:1063-1080,2557`。

stager 初期化で CUDA/HIP の event 作成または SYCL の host memory / event 作成に失敗すると `Prefill::init` は失敗する。呼び出し元は `strata generate: <err>` を stderr に出して終了コード 1 を返す。エラー文字列は ring 専用ではなく `prefill: host buffers or events for a chunk of <N> tokens`。SYCL 例外は catch 節で例外文字列と file/line を stderr に出し `exit(1)` する。`engine/src/prefill/prefill.cpp:1156-1171,2632`、`engine/sycl/src/prefill/prefill.cpp:502-534,1596,1635-1638`、`engine/src/program/generate.cpp:24118-24123`、`engine/sycl/src/program/generate.cpp:13354-13359`。

## 根拠

- `engine/src/prefill/prefill.cpp:1121-1129,1156-1162,1205-1248,1297-1305,2523-2557`
- `engine/sycl/src/prefill/prefill.cpp:464-515,567-638,1389-1403,1491-1505,1596,1635-1638`
- `engine/src/program/generate.cpp:24118-24123`
- `engine/sycl/src/program/generate.cpp:13354-13359`
