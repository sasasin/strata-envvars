# `DS4_MV_LOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更はありません。

## 役割

DeepSeek V4.1 エンジンの Metal 実装で、GGUF matvec に渡された job 数を集計し、256 回ごとに累積値を stderr に出す診断用スイッチです。モデル計算や job の選択を変更せず、実行性能を調整する設定でもありません (`src/dsv41/ds4_gguf.cu:1173-1191`)。

CMake では DeepSeek V4.1 エンジン自体が `STRATA_BUILD_DSV41` で選択され、既定 OFF です (`CMakeLists.txt:906-920`)。

## 値と判定

`ds4_dbg("DS4_MV_LOG")` は Metal ビルドでは `std::getenv(name) != nullptr` を返します。値の文字列は変換・比較されません (`src/dsv41/ds4_launch.h:30-36`)。

| 環境変数の状態 | Metal での判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を設定 | 有効 |
| 任意の非空文字列（`0`、`false` を含む） | 有効 |

CUDA/HIP など `STRATA_METAL` 以外では、同 helper はコンパイル時定数 `false` で、診断分岐も `#if defined(STRATA_METAL)` の内側です。そのため設定値にかかわらず、このログ処理は動きません (`src/dsv41/ds4_launch.h:30-36`, `src/dsv41/ds4_gguf.cu:1173-1191`)。

## 有効になる条件

- Metal 向けにコンパイルされた DeepSeek V4.1 エンジンの matvec 経路であること。
- `gg::mv()` が呼ばれ、job 数 `n` が `1..x3::kMaxMvJobs` の範囲にあること。範囲外なら関数はログ判定前に `false` を返します (`src/dsv41/ds4_gguf.cu:1173-1175`)。
- 呼び出し元 `mv_any()` は、job に `fmt != 0` の行列が一つでもある場合に `gg::mv()` へ渡します。全 job が EXL3 (`fmt == 0`) の場合は `x3::mv()` へ行き、このカウンターには入りません (`src/dsv41/ds4_model.cu:7639-7653`)。

対応する CLI 引数、別環境変数との優先順位、値の clamp/fallback はありません。CMake の `STRATA_BUILD_DSV41` が OFF ならこのエンジンもビルドされません (`CMakeLists.txt:906-920`)。

## 実行時の詳細

有効判定は有効な `gg::mv()` 呼び出しごとに `getenv()` で行われ、環境値の真偽を static cache しません。したがって判定時点で変数が設定されていればその呼び出しのカウントを加算します。集計用の `calls`、`jobsum`、job 数別 `hist`、出力間隔用 `seen` は関数内 static atomic でプロセス内に保持されます (`src/dsv41/ds4_gguf.cu:1173-1182`)。

有効な呼び出しでは `calls` に 1、`jobsum` に `n`、`hist[n]`（`n >= 8` は bucket 8）に 1 を加算します。設定後 256 回目、および以後 256 回ごとに stderr へ次の形式を出します (`src/dsv41/ds4_gguf.cu:1176-1189`)。

```text
mvlog calls=... jobs=... avg=... hist1..4=...,...,...,... 5+=...,...,...,...
```

数値はログ時点までの累積 call 数・job 数・平均 job 数と bucket 1〜8 の回数です。変数未設定時や上記以外の backend ではこのログは出ません。この変数に起因する警告、エラー、終了経路はありません。診断分岐の後は通常の matvec job 処理に進みます (`src/dsv41/ds4_gguf.cu:1192-1205,1269-1270`)。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — `ds4_dbg` の Metal 環境参照と非 Metal の定数 false。
- `src/dsv41/ds4_gguf.cu:1173-1191` — job 数の境界判定、Metal 限定の環境判定、集計および stderr 出力。
- `src/dsv41/ds4_gguf.cu:1192-1205,1269-1270` — ログ後に続く通常の job 処理。
- `src/dsv41/ds4_model.cu:7639-7653` — GGUF matvec と EXL3 matvec の振り分け、および呼び出し経路。
- `CMakeLists.txt:906-920` — DeepSeek V4.1 エンジンの任意ビルド設定と実行ファイルのソース構成。
