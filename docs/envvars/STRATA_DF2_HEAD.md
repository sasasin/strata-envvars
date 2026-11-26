# `STRATA_DF2_HEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--draft dflash2` を使うとき、DFlash2 の draft head をドラフト語彙に合わせた行のコピーで動かすか、target モデルが常駐させている head 全体で動かすかを切り替える。CUDA/HIP 共通実装では、同一 GPU 上の head に限り、ドラフト語彙ファイルを読まずに全行を使う。Metal 実装では head を Q8_0 に再量子化した draft 用コピーを作らず、target の head 全体を使う（`engine/include/strata/core/dflash2.hpp:55-56`、`engine/src/core/dflash2.cpp:388-405`、`engine/metal/src/engine/dflash2.inc:317-328`）。

この変数は通常の生成 head や MTP drafter 自体を切り替えない。DFlash2 を選択し、その drafter の head を bind する経路でのみ関係する。特に CUDA/HIP の複数 GPU の layer split で head が drafter と別 GPU にある場合、`native` 判定が真でも全 head の in-place 利用にはならず、従来どおり語彙行を集めてコピーする（`engine/src/core/dflash2.cpp:388-390,413-440`）。

## 値と判定

両実装とも環境から文字列を直接読み、数値変換や空白除去はしない。ただし有効判定は backend ごとに異なる。

| 実装 | 未設定 | head 全体モードになる値 | ならない値 |
|---|---|---|---|
| CUDA/HIP 共通 (`head_native`) | 無効 | 先頭バイトが小文字 `n`。例: `n`, `native`, `no`, `native-extra` | 空文字、`0`, `1`, `true`, `false`, `Native`, ` native` |
| Metal の最終 bind 判定 | 無効 | 文字列全体が大文字小文字を区別して `native` と一致 | 空文字、`n`, `no`, `native-extra`, `Native`, ` native`, `0`, `1`, `true`, `false` |

CUDA/HIP は `getenv(...) != nullptr && e[0] == 'n'` だけを見るため、空文字は設定済みでも無効であり、`native` という完全一致は要求しない（`engine/include/strata/core/dflash2.hpp:56`）。Metal の最終 bind は `hm && std::string(hm) == "native"` で完全一致する（`engine/metal/src/engine/dflash2.inc:319-322`）。一方、共通の起動処理にある語彙ファイル解決の省略判定は `head_native()` を使うので、Metal でも `n` で始まる値は語彙解決を省略するが、最終 bind では `native` 完全一致でない限り全 head モードにならない（`engine/src/program/generate.cpp:6510-6528`）。この判定を CLI 引数や別の環境変数で上書きする処理は確認できない。

## 有効になる条件

- DFlash2 が使われ、target head の bind 処理まで到達する必要がある。通常は `--draft dflash2` の選択と pack (`--draft-model`) など DFlash2 の起動条件が満たされる必要がある（`engine/src/program/generate.cpp:6501-6508,13584-13595,24512-24525`）。
- CUDA/HIP では draft 語彙ファイルが非空で、かつ head が drafter と同じ GPU にある場合に、語彙ファイル読込と行の pruned copy を省く。ファイルが空または開けない場合は語彙行が空のままなので、もともと全行を使う経路となり、この変数による語彙ファイル省略の差はない（`engine/src/core/dflash2.cpp:388-405,413-468`）。別 GPU の head では `head_device < 0 || head_device == device_` が成立せず、環境変数が有効でも従来の行コピー経路を使う（同 `:390,413-440`）。
- Metal では DFlash2 の `df2_bind` が呼ばれたときに値を判定する。`native` の場合は先に用意された語彙候補を消し、全 head 行を使う。`native` 以外では候補語彙に基づく Q8_0 head を用意する（`engine/metal/src/engine/dflash2.inc:297-328`）。Metal のビルドでこの実装を含むことは `engine/metal/src/engine/window.cpp:3791-3793` と `engine/metal/CMakeLists.txt:154-156` にある。
- SYCL の DFlash2 bind は語彙ファイルから行を集めるが、この変数を読む処理も `head_native()` 呼び出しもないため、この環境変数による切替はない（`engine/sycl/src/core/dflash2.cpp:284-332`、起動側 bind は `engine/sycl/src/program/generate.cpp:13775`）。
- CUDA/HIP では `head_native()` が呼ばれるたびに `getenv` を評価し、関数内 static には保存しない。実行中に環境値を変更した場合の動作はソース上保証されない。Metal は bind 時に読み、すでに bind 済みなら `Dflash2Drafter::bind` は早期 return する（`engine/include/strata/core/dflash2.hpp:56`、`engine/metal/src/engine/dflash2.inc:1059-1066`）。

## 実行時の詳細

CUDA/HIP の bind は head 全体を参照する通常状態から始まり、語彙ファイルを正常に読めた場合はその ID 群を使う。`STRATA_DF2_HEAD` が有効かつ head が同じ GPU にあれば語彙ファイルを読まず、`head_rows` は target head の全行数のまま `bind_raw` に渡される。これにより target head の pruned copy と語彙 ID 配列を作らず、全語彙行の logits 用バッファが必要になる。語彙ファイルがあり同じ GPU でない場合は環境変数が有効でも従来の subset copy を行う（`engine/src/core/dflash2.cpp:388-405,413-470`）。生成側の VRAM 見積りも `head_native()` が真なら全行 logits 分を見積もる（`engine/src/program/generate.cpp:8421-8432`）。

Metal は bind 時に `STRATA_DF2_HEAD` を一度読み、完全一致 `native` なら `vocab.clear()` として全語彙行を対象にし、`head_q8` を false にする。それ以外は `head_q8` が true のままで、候補語彙の head 行を Q8_0 に変換する（`engine/metal/src/engine/dflash2.inc:317-355`）。

この設定による生成結果の一致・相違や速度差は、実行測定を行っていないため記載しない。コード上、Metal の Q8_0 変換経路と target head の直接 GEMV 経路では計算経路が異なる（`engine/metal/src/engine/dflash2.inc:328-355`）。

## ログと測定値

変数の値そのものを報告するログや、無効値の警告はない。CUDA/HIP の bind 成功時には `strata dflash2: %lld-token draft head ...` を stderr に出し、選択された head 行数を確認できる（`engine/src/core/dflash2.cpp:470-475`）。bind に失敗すると、たとえば native head 未ロード時は `dflash2: the drafter needs the native head (--native)`、全行利用時に logits 確保できないと `dflash2: the draft logits do not fit` が返る（同 `:371-374,363-365`）。生成・serve 側は失敗理由を `strata generate: --draft dflash2: ...` または `strata serve: --draft dflash2: ...` として出し、MTP fallback の有無に応じて fallback または起動終了する（`engine/src/program/generate.cpp:13593-13606,24517-24529`）。

## 根拠

- `engine/include/strata/core/dflash2.hpp:54-56`
- `engine/src/core/dflash2.cpp:347-367,371-476`
- `engine/src/program/generate.cpp:6501-6524,8404-8432,13584-13614,24512-24529`
- `engine/metal/src/engine/dflash2.inc:297-355,1059-1066`
- `engine/metal/src/engine/window.cpp:3791-3793`
- `engine/metal/CMakeLists.txt:154-156`
