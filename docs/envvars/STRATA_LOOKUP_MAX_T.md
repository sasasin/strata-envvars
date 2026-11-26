# `STRATA_LOOKUP_MAX_T`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は lookup 窓の最大 token 数を数値で指定する設定ではなく、条件を満たす `strata serve` で自動選択される `--lookup-max-t 12` を抑止する off スイッチである。`STRATA_LOOKUP_MAX_T` の先頭文字が `0` なら、CLI で値が指定されていない場合の既定値を 0 にする。それ以外の値は既定値を有効化せず、既定値判定に影響しない。読み取りと既定値の適用は `engine/src/program/generate.cpp:5040-5055`、判定関数は `engine/include/strata/core/lookup_default.hpp:9-28`。

lookup 窓が有効な場合、server は許可された幅を DraftPolicy に渡し、prompt の読み込みと decode の lookup 窓でその幅を使う。各幅の verifier graph を事前に準備し、VRAM 不足なら該当幅を候補から外して小さい幅を試す（`engine/src/program/generate.cpp:16429-16431,16512-16529,20431-20446,22737-22741`）。この変数自身が token 内容や最大幅を指定するものではない。

## 値と判定

環境変数は `std::getenv` で読み、未設定かどうかと `lme[0] == '0'` だけを判定する。数値変換、文字列全体の比較、空白除去、大小文字変換はしない（`engine/src/program/generate.cpp:5043-5046`）。

| 条件 | unset | 先頭が `0` の例 | その他の例 |
|---|---|---|---|
| CLI が `--lookup-max-t` を指定していない | 環境変数による抑止なし。下記の既定値条件で最大 12、その他は 0 | 既定値を 0 にする（`0`, `0anything`, `00`） | 抑止なし。空文字、`1`, `true`, `false`, ` 0`, `0.5` 以外の非ゼロ始まり文字列も同じ扱い |
| CLI が `--lookup-max-t N` を指定 | 環境変数を読まず CLI 値を使用 | 同左 | 同左 |

CLI 値の初期値は `-1`。`--lookup-max-t` 指定時は `atoi` の結果を 0 以上にして保存するため、`--lookup-max-t 0` は明示的な off、負数や数値に変換できない文字列も 0 になる。CLI 値が `-1` 以外なら環境変数の読み取り分岐に入りません（`engine/src/program/generate.cpp:1173,4123,5043-5055`）。

環境変数で抑止しない場合でも、既定値が 12 になるのは次の条件がすべて真の場合だけ。それ以外は 0（`engine/include/strata/core/lookup_default.hpp:9-28`）。

- ビルドの `kVerifyMaxT` が `kVerifyNarrowT` と等しい（現在の共通定義では 8 行）。
- Metal ビルドではない。
- serve モードで、multi-GPU でも layer split でもない。
- `--batch` が 1 以下、DFlash2 を使わず、`--lookup-chain` が 0。
- suffix draft が有効で、`--spec` が 2 以上。

`generate.cpp` を含む共通 GPU engine target は CUDA / HIP 用（`engine/CMakeLists.txt:22,714`, `engine/cmake/strata_gpu_engine.cmake:1,548`）。この build では `STRATA_WINDOW_MAX_T=auto` が CUDA で 8、HIP で 16 になる。したがって標準の CUDA 8 行 build は幅条件を満たし、標準の HIP 16 行 build は満たさない。明示的に 8 または 12 行を選んだ場合、`kVerifyMaxT == 8` の判定が真になるのは 8 行だけ（`engine/CMakeLists.txt:116-138`, `engine/include/strata/kernels/window_limits.hpp:14-25`, `engine/src/program/generate.cpp:5046-5054`）。

## 有効になる条件

- `STRATA_LOOKUP_MAX_T` が自動既定値を抑止できるのは、`--lookup-max-t` が CLI で指定されていない場合だけ。CLI 指定は環境変数に優先する（`engine/src/program/generate.cpp:4123,5043-5055`）。
- 環境変数が設定されても lookup を有効化はしない。lookup を有効にする自動条件は前節の全条件であり、`STRATA_LOOKUP_MAX_T` の unset または先頭文字が `0` 以外であることも必要（`engine/include/strata/core/lookup_default.hpp:23-28`）。
- 自動既定値が 0 でも、CLI の `--lookup-max-t N` に正値を指定すれば別経路で有効にできる。指定値は `--spec` の上限検査や build の窓幅制約を受ける（`engine/src/program/generate.cpp:4123,5079-5098`）。
- lookup が有効でも layer split では許可サイズを narrow 窓までに絞り、`--spec` も上限 8 に戻す。既定値判定は layer split を除外するが、CLI で明示的に有効化した場合にはこの制限経路が適用される（`engine/src/program/generate.cpp:13256-13261,16429-16431`）。
- lookup 最大値が build の `kVerifyMaxT` を超え、`STRATA_GDN_SPLIT=1` のときは、その設定が既定由来なら Strata が環境から削除し、ユーザー設定なら lookup 幅を `kVerifyMaxT` に clamp する（`engine/src/program/generate.cpp:5056-5076`）。

## 実行時の詳細

オプション初期値は `lookup_max_t = -1`。CLI 引数解析後、共通のオプション調整でこの値が負のときにだけ `std::getenv("STRATA_LOOKUP_MAX_T")` を呼び、既定値を決める（`engine/src/program/generate.cpp:1173,4123,5043-5055`）。static cache やリクエスト単位の再読ではなく、起動時の一度の判定であるため、プロセス起動後に環境を変更しても反映されない。Strata がこの値を子プロセスへ転送する実装は見つからなかった。

lookup 最大値が正なら `lookup_size_mask` が DraftPolicy 用の候補サイズを作る。通常は MTP のサイズに加え、既定では MTP 最大値の次の 1・2 token と上限幅が候補になる。serve は起動時の window warm-up と各 prompt / decode の lookup 判定でその候補を使う（`engine/src/program/generate.cpp:1507-1528,16348-16373,16429,20431-20446,22712-22741`）。候補幅の graph に VRAM が足りない場合、その幅を policy から外して次に小さい幅へ進む。VRAM 以外の graph 準備失敗は `ERR` 経路に進む（`engine/src/program/generate.cpp:16515-16529,22737-22741`）。

## ログと測定値

`STRATA_LOOKUP_MAX_T` 自体の値を表示するログはない。lookup 最大値が正のとき、serve は `strata serve: --lookup-max-t %d: MTP windows up to %d tokens, window sizes %s` を stderr に出す（`engine/src/program/generate.cpp:16512-16514`）。この行が出ないことだけから環境変数が設定されたとは判定できない。既定値 0、CLI による off、条件外も同じく lookup 最大値が正にならない。

VRAM 不足の候補幅は `strata serve: no VRAM for the %d-token window graph: that size is dropped, sizes left %s (a larger --vram-reserve-mib keeps it)` と stderr に記録される。graph 準備が VRAM 不足以外で失敗した場合、decode 側は `ERR %s` を stdout に出して return 1 する（`engine/src/program/generate.cpp:16518-16529,22737-22741`）。

`docs/DETAILS.md:1277` は関連する CLI 機能について、file rewrite / agent edit turn で RTX A6000 IQ3_S の +11〜14%、Tesla P100 IQ3_XXS の +13〜18%、通常の prose / code は 12 幅で 1% 以内と記載している。これは同資料にある報告値であり、この調査で再測定した値ではない。同節では追加条件・反復回数・OS を示していないため、ここでは環境変数の効果として一般化しない。

## 根拠

- 変数読み取り、CLI 優先順位、既定値入力: `engine/src/program/generate.cpp:1173,4123,5040-5055`
- 既定値の全条件: `engine/include/strata/core/lookup_default.hpp:9-28`
- build ごとの最大窓と GPU engine target: `engine/CMakeLists.txt:22,116-138,714`, `engine/cmake/strata_gpu_engine.cmake:1,548`, `engine/include/strata/kernels/window_limits.hpp:14-25`
- 候補サイズ、warm-up、serve のログと VRAM fallback: `engine/src/program/generate.cpp:1507-1528,16348-16389,16429-16431,16512-16529`
- layer split / GDN split の制限: `engine/src/program/generate.cpp:5056-5076,13256-13261`
- prompt と decode における使用箇所: `engine/src/program/generate.cpp:20431-20446,22712-22741`
- 関連機能の資料値: `docs/DETAILS.md:1277`
