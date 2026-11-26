# `STRATA_DF2_STAGE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA/HIP ビルドで DFlash2 drafter をレイヤー分割のどの stage に置くかを切り替える、計測用の環境変数。通常は最後の stage に置き、`STRATA_DF2_STAGE=first` のときだけ最初の stage に置く。DFlash2 の計算方式や CLI オプション値を変える処理ではなく、配置先の選択に使われる（`engine/src/program/generate.cpp:6738-6744,8273-8275`）。

実際の読み取りは `generate.cpp` の `df2_first` 判定 1 箇所だけ。名前の他の参照は同ファイルのコメントと `terminal/data/settings-register.json` の設定レジストリ項目で、後者はソースでの読み取りではない。

## 値と判定

`std::getenv` で値を取得し、未設定でない場合に `std::string(e) == "first"` で文字列全体を比較する。空文字、`0`、`1`、`true`、`FIRST`、`first ` は一致せず、既定の最後の stage が使われる。大文字小文字を区別し、trim、数値変換、部分一致はしない。`first` が有効値で、それ以外はこの切替に対して無効値（最初の stage を選ばない）となる（`engine/src/program/generate.cpp:6740-6744`）。

| 条件 | unset | 最初の stage を選ぶ値 | 最初の stage を選ばない値 |
|---|---|---|---|
| `multi_gpu` で DFlash2 を明示選択し、`--draft auto` ではない | 最後の stage | 完全一致の `first` | 空文字、`0`、`1`、`true`、`FIRST`、`first ` など |
| 上記以外 | 配置切替の判定は常に false | なし | 全て（環境変数を読まない） |

## 有効になる条件

- DFlash2 対応の CUDA または HIP ビルドであること。GPU 共通 CMake 設定は CUDA/HIP の場合に `STRATA_HAVE_DFLASH2=1` を定義し、Metal/SYCL は DFlash2 なしでビルドすると記載している（`engine/cmake/strata_gpu_engine.cmake:6-13`）。DFlash2 本体のロード処理はこの macro の下にある（`engine/src/program/generate.cpp:8266-8275`）。
- 複数 GPU のレイヤー分割が実際に残っていること。1 GPU になった場合や `--split-skip-if-fits` で分割が解消された場合は `multi_gpu` が false となり、この環境変数では配置を変えない（`engine/src/program/generate.cpp:4856,6472-6484`）。
- `--draft dflash2` を明示し、`--draft auto` を使わないこと。CLI は `auto` を内部で DFlash2 に変換しつつ `draft_auto` を立てるため、環境変数の条件から除外される（`engine/src/program/generate.cpp:4143-4149,6740-6744`）。`--draft mtp` でも効かない。
- DFlash2 のロード自体が可能であること。通常経路では native pack、必要な fallback / `--mtp`、`--draft-model`、`--pipeline-windows 0` などの条件を別途確認し、ロード失敗時は fallback 設定に応じて MTP に切り替えるか起動を終了する（`engine/src/program/generate.cpp:8266-8275,8310-8326`）。この環境変数はその条件や失敗を上書きしない。
- serve のレイヤー分割でも同じ stage 選択値が使われる。DFlash2 の stage ごとの prompt tap を drafter 側へ集める準備は、配置先とは別に必要となる（`engine/src/program/generate.cpp:13584-13613`）。

## 実行時の詳細

環境変数は stage 構築後、split の配置・容量計画に入る箇所で評価される。`df2_first` が true なら split 自動配置時に最初の stage の容量を drafter 分として見積もり（`engine/src/program/generate.cpp:6959-6972`）、通常起動では DFlash2 を device 0 にロードする。false なら複数 GPU 時は最後の stage の device にロードする（`engine/src/program/generate.cpp:8273-8275`）。レイヤー分割は primary device 0 を前提としており、別 primary device との組み合わせは拒否される（`engine/src/program/generate.cpp:4856-4863`）。

serve 経路では true の場合に first stage、false の場合に last stage を drafter の重み元・配置先として選び、全 verifier stage の tap を drafter 側に集める。成功時の起動ログには `layer split: the drafter is on CUDA... (first|last stage), the other stages' taps are gathered onto it` と配置が出る（`engine/src/program/generate.cpp:13588-13595,13607-13613`）。通常の CLI 起動ログは DFlash2 の起動を示すが、この環境変数専用のログはない（同 `:8273-8324`）。

値はこの初期化時の式で読み、`static` cache は使わない。リクエスト単位の再読み込み箇所はなく、serve のリクエスト処理はこの判定より後に進む（`engine/src/program/generate.cpp:6740-6744,18862-18944`）。起動後にプロセス環境を変えても、既に決まった stage 配置は切り替わらない。

## ログと測定値

serve の成功ログでは選ばれた CUDA device 番号と `first stage` / `last stage` を確認できる（`engine/src/program/generate.cpp:13610-13613`）。無効値や未設定だけを理由にした警告・エラーはなく、通常配置のまま進む。DFlash2 自体のロード失敗は `--draft-fallback` に応じた起動ログまたは終了経路となり、この変数による専用の失敗経路ではない（同 `:8310-8324`）。

`docs/DETAILS.md` にこの変数の stage 切替に関する測定値はなく、この調査でも測定していない。

## 根拠

- `engine/src/program/generate.cpp:6738-6744` — 既定配置、条件判定、唯一の `getenv` 読み取り。
- `engine/src/program/generate.cpp:4143-4149,4856-4863,6472-6484` — `--draft auto` の内部表現、multi-GPU 条件、分割解消条件。
- `engine/src/program/generate.cpp:6959-6972,8266-8275,8310-8326` — 自動配置計画、DFlash2 のロード先と起動可否。
- `engine/src/program/generate.cpp:13584-13613` — serve の stage binding、tap 集約、観測できる配置ログ。
- `engine/cmake/strata_gpu_engine.cmake:6-13` — DFlash2 を含む CUDA/HIP build macro。
- `docs/DETAILS.md:1237-1246` — DFlash2 の一般的な測定記述はあるが、この stage 選択変数の測定値は記載されていない。
