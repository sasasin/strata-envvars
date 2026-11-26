# `STRATA_DF2_FORK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

DFlash2 の speculative draft graph を作るとき、コンテキスト更新とブロックの前半を別 GPU stream に分けて重ねるかを選ぶ。ON のときはコンテキスト更新を `cs2_`、ブロック処理を `cs_` に記録し、各レイヤーの attention 前にイベントで合流する。後段の head と selector hidden projection も条件を満たせば別 stream で重ねる。OFF のときは同じ `cs_` に順に記録する。対象は DFlash2 の処理順序と stream 配置であり、この変数による出力内容の同一性はソースからは確認できない（`engine/src/core/dflash2.cpp:589-613, 621-643`）。

DFlash2 は CUDA / HIP ビルドに組み込まれ、Metal / SYCL ビルドには含まれない。したがって、この変数の読み取りも CUDA / HIP の DFlash2 実装だけで行われる（`engine/cmake/strata_gpu_engine.cmake:12-13, 312`）。

## 値と判定

`capture()` 内の関数ローカル `static const bool` を初期化するとき、`std::getenv` の戻り値と先頭文字だけを見る。変換・数値 parse・文字列全体の比較はしない。unset または空文字はビルド別の既定値になり、それ以外は先頭が ASCII `1` の場合だけ ON。先頭が `1` 以外の非空文字列は既定値に戻らず OFF になる（`engine/src/core/dflash2.cpp:627-634`）。

| ビルド | unset / 空文字 | 設定時に ON | 設定時に OFF |
|---|---|---|---|
| CUDA（`STRATA_USE_HIP` 未定義） | ON | `1`, `10`, `1anything` | `0`, `true`, ` 1`, `01`, その他先頭が `1` でない非空文字列 |
| HIP（`STRATA_USE_HIP` 定義） | OFF | `1`, `10`, `1anything` | `0`, `true`, ` 1`, `01`, その他先頭が `1` でない非空文字列 |

大文字小文字や空白の除去はなく、`true` / `false` は真偽値として解釈しない。`10` や `1anything` も先頭が `1` なので ON になる。無効な文字列を示すエラーや警告はない（同 `:628-634`）。

## 有効になる条件

- DFlash2 が利用可能な CUDA または HIP ビルドであること。Metal / SYCL には DFlash2 自体が組み込まれない（`engine/cmake/strata_gpu_engine.cmake:12-13`）。
- 実行時に DFlash2 が選択され、モデル・draft pack・verifier の準備を通って `Dflash2Drafter::prepare()` または初回の未作成 graph 用 `capture()` に到達すること。CLI では `--draft dflash2` の条件を満たして pack をロードし、bind / prepare する経路があり、serve も DFlash2 を bind / prepare する（`engine/src/program/generate.cpp:8266-8275, 13584-13610, 24512-24531`）。
- `STRATA_DF2_PROFILE=1` により profile モードになっていないこと。profile 時は `prepare()` が graph capture を行わず、draft も graph なしで同一 stream に記録されるため、この変数の static 判定は行われず、fork も使われない（`engine/src/core/dflash2.cpp:296, 752-760, 1198-1208`）。
- `capture()` の判定は `fork_on && prof_ == nullptr && cs2_ != nullptr`。この実装では `make_streams()` が `cs2_` を作成し、作成失敗時は `dflash2: stream` で初期化に失敗する（`engine/src/core/dflash2.cpp:271-302, 633-634`）。

## 実行時の詳細

環境値はプロセス起動時ではなく、DFlash2 の最初の graph capture 時に `fork_on` の初期化として一度だけ読み取られる。以後の capture は同じ static 値を使うため、実行中に環境値を変えても反映されない。profile モードで capture 自体が起きない場合は読み取りも起きない（`engine/src/core/dflash2.cpp:621-634, 752-760, 1174-1185`）。

fork が有効なら、capture 開始イベントを `cs2_` に待たせてから `record_context()` を `cs2_` に記録し、`record_block()` を `cs_` に記録する。前者は `fc` と各レイヤーの K/V ring 更新を含み、後者は DFlash2 の draft block を実行する。block 側は各レイヤーの attention で、そのレイヤーの K/V 更新完了イベントを待つ。最後に `cs_` が `cs2_` の完了を待つ graph を記録する（`engine/src/core/dflash2.cpp:493-536, 539-566, 621-655`）。selector hidden projection と head/top-k も `cs2_` と `cs_` 間のイベントで重ねる分岐がある（同 `:589-613`）。

fork が無効なら `record_context()` と `record_block()` はともに `cs_` に記録される（同 `:639-643`）。この変数は CUDA graph の構築時に使われ、draft のたびに環境を読み直すものではない。

## ログと測定値

この変数を読んだことや ON / OFF を示す専用ログはない。capture の失敗時は `dflash2: capture: <CUDA/HIP runtime のエラー文字列>` などが error に入り、CLI の DFlash2 起動経路では `strata generate: --draft dflash2: ...` を stderr に出して通常は MTP にフォールバックする。`--draft-fallback none` の場合は起動を終了する（`engine/src/core/dflash2.cpp:645-650`; `engine/src/program/generate.cpp:8310-8323, 24525-24535`）。

ソースコメントには、RTX 3060 で 1 ラウンドあたり `-0.3 ms`、Strix Halo（gfx1151）で `+0.0..0.7 ms` とあり、HIP では既定で single stream にすると説明されている。ただしモデル、OS、計測手順・回数などの条件はこのコメントに記載されていないため、一般的な性能差としては扱えない（`engine/src/core/dflash2.cpp:626-631`）。

## 根拠

- `engine/src/core/dflash2.cpp:621-655` — 値の読み取り、CUDA/HIP 別既定値、fork の条件、stream 間のイベントと graph capture。
- `engine/src/core/dflash2.cpp:271-302, 493-566, 589-613` — 2 本の stream の作成、コンテキスト更新・ブロック処理・selector の処理内容。
- `engine/src/core/dflash2.cpp:752-760, 1174-1208` — graph capture の呼び出し時期と profile 時の経路。
- `engine/src/program/generate.cpp:8266-8326, 24512-24535` — CLI で DFlash2 を選び、準備に失敗した場合の fallback / 終了。
- `engine/cmake/strata_gpu_engine.cmake:12-13, 312` — DFlash2 実装を CUDA / HIP ビルドに含める条件。
