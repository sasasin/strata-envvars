# `--threads`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。Strata checkout は branch `main` で `origin/main` と同期し、`git status --short --branch` は `## main...origin/main`（変更なし）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl`（root） |
| オプション | `--threads N` |
| 別名 | なし |
| 値 | `N` を `atoi` で整数化。正の値は画像エンコーダーのスレッド数として渡される。 |

## 役割

画像読み取り CLI が画像をエンコードするときのスレッド数を指定します。これは `strata` Terminal CLI のオプションではなく、画像エンコーダー用の独立実行ファイルに渡します。`strata-vision` は CPU 版、`strata-vision-hip` と `strata-vision-sycl` は CMake の build 設定で生成される GPU 版の別名です（`tools/vision/CMakeLists.txt:18-20,96-116`）。

## 使い方

```sh
strata-vision --mmproj ./mmproj.gguf --model ./model.gguf --threads 8
```

この CLI は起動時に `--mmproj` と `--model` を必要とします。GPU 版で指定する場合も同じ `--threads N` を使用します（`tools/vision/strata_vision.cpp:7-8,99-115,125-128`）。

## 値と既定値

- `N` は次の argv 要素として読み取られ、`std::atoi` で整数に変換されます。値が省略されている場合は `--threads needs a value` を stderr に出し、終了コード 2 で終了します（`tools/vision/strata_vision.cpp:93-98,114`）。
- 数値形式や正の範囲を検証する処理はありません。正の値だけが `cp.n_threads` に設定され、0 または負数は設定されません（`tools/vision/strata_vision.cpp:227-228`）。
- CPU 実行時に省略するか、変換後の値が 0 以下なら、`hardware_concurrency() / 2` を 1 以上 16 以下に収めた値を使います。したがって既定数は検出された hardware concurrency の半分（整数除算）を基準にし、最大 16、最小 1 です（`tools/vision/strata_vision.cpp:225-228`）。
- `--gpu` とともに省略するか、値が 0 以下の場合、上記 CPU 用の自動計算は適用されず、`mtmd_context_params_default()` が返す `cp.n_threads` の値をそのまま使います。Strata のこのソースでは外部 mtmd ライブラリの既定スレッド数までは定義していません（`tools/vision/strata_vision.cpp:214-215,225-228`）。

## 実行時の動作

parser はオプション値を `threads` に保存します。モデルファイルを開いた後、`mtmd_context_params_default()` で初期化した設定の `n_threads` に、正の `threads` を設定して画像エンコーダーの context 作成関数 `mtmd_init_from_file()` に渡します（`tools/vision/strata_vision.cpp:88-91,114,208-231`）。この値は Strata エンジン全体やサーバーの worker 数ではなく、この画像読み取りプロセス内で mtmd に渡す設定です。

CPU 実行時には `--threads` 未指定または 0 以下なら自動算出値を採用し、正数なら指定値で上書きします。GPU 実行時には CPU 用の自動算出を行わず、正数を指定したときだけ `cp.n_threads` を上書きします（`tools/vision/strata_vision.cpp:101,214-228`）。CPU 実行ではモデルの読み込み後に `strata-vision: on the CPU, %d threads, no warm-up` を stderr に出します。GPU 実行ではこのログ行は出ません（`tools/vision/strata_vision.cpp:255-256`）。

## 適用条件と副作用

- CPU 用の自動値は `!gpu` の場合だけ適用されます。`--gpu` は別フラグであり、`--threads` 自体が GPU の使用を有効にすることはありません（`tools/vision/strata_vision.cpp:101,225-228`）。
- 指定値の上限検査やハードウェア数に対する clamp はありません。正の値はそのまま `cp.n_threads` に渡されます。実際の thread pool の生成・スケジューリングや不正な大値の扱いは mtmd/依存ライブラリ側に委ねられており、この Strata ソースだけからは確認できません。
- このオプションの parser は値を環境変数や設定ファイルと照合しません。調査対象コードで確認できる相互作用は `--gpu` による CPU 自動値の分岐です（`tools/vision/strata_vision.cpp:93-124,225-228`）。

## 出力とエラー

- 値のない `--threads` は stderr にエラーを出し、終了コード 2 で終了します（`tools/vision/strata_vision.cpp:95-98`）。
- `--threads` を含む未知の引数は `unknown argument <引数>` を stderr に出し、終了コード 2 で終了します（`tools/vision/strata_vision.cpp:123`）。
- 値そのものの不正形式や範囲を理由に Strata が明示的に拒否する経路は見つかりません。`atoi` の戻り値に対する validation はありません（`tools/vision/strata_vision.cpp:114,225-228`）。

## 根拠と調査範囲

主な根拠は `tools/vision/strata_vision.cpp:88-128`（引数 parser）、`:214-231`（thread 数の決定と mtmd context への設定）、`:255-256`（CPU 実行時ログ）、および `tools/vision/CMakeLists.txt:18-20,96-116`（実行ファイルと build variant）です。対象 checkout は clean で、変更中のソースはありません。安全に実行できる同一 revision の既存 CLI help は確認しておらず、説明は parser と使用箇所のソース調査に基づきます。mtmd 内部の既定値・thread 動作、各 build variant の実機動作はこの調査では検証していません。
