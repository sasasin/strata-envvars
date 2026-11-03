# `STRATA_METAL_SAMPLE_STATS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンの sampler 呼び出し回数と直近の sampler graph 実行時間を、200 回ごとに stderr へ出す診断用フラグです。サンプリングの計算や選択結果を変更する分岐ではありません。

対象処理は Metal の `Window::sample_run()` です。通常の window sampling と batch slot ごとの sampling のどちらもこの関数を通ります（`metal/src/engine/window.cpp:3145-3156,3160-3161`）。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 設定あり（空文字を含む） | 有効 |

値の文字列や数値への変換はありません。`std::getenv(...) != nullptr` の結果だけを使うため、`0`、`false`、任意の文字列、空文字はいずれも設定されていれば有効です。CLI 引数や他の環境変数による上書き・優先順位は実装されていません。根拠: `metal/src/engine/window.cpp:3225`。

## 有効になる条件

- `metal/` のエンジンを含む Strata Metal ビルドであること。CMake は macOS 以外を拒否し、Metal runtime 用の `METAL_CPP_DIR` がない場合は engine を構成せず、`STRATA_METAL_ENGINE` が無効なら engine を作りません（`metal/CMakeLists.txt:16-18,51-55,73-76`）。
- 実行時に `Window::sample_run()` が呼ばれること。通常経路では `sample_rows()` が sampling 有効かつ `Tn` が 1..`MAXT` のとき実行され、Metal の `window_run()` は `head` が真のとき `sample_rows()` を呼びます（`metal/src/engine/window.cpp:3145-3149,3297-3303`）。Verifier は sampled / penalised / biased request のとき sampler 設定を渡し、それ以外では無効にします（`src/core/verify.cpp:3240-3250`）。batch slot 経路も `sample_slot_row()` から同じ関数を呼びます（`metal/src/engine/window.cpp:3152-3156,3291-3292`; 呼び出し元 `src/core/verify.cpp:4666-4676`）。CLI/server の別設定でこの診断フラグの値を上書きする処理は見つかりません。
- vocab 幅が `64 * 4096` 以下であること。超えると sampler graph の前に `false` を返し、`err` に `metal sampler: the vocabulary is wider than 64 parts of 4096` を設定するため、計測行には到達しません（`metal/src/engine/window.cpp:3160-3165`）。

CUDA/HIP/SYCL のサンプラーでこの変数を読む箇所はありません。候補名の Strata ソース全体の参照は `metal/src/engine/window.cpp:3225` のみです。

## 実行時の詳細

sampler は `cx_->run_graph({d1, d2})` の直前に `now_ms()` を取り、graph 呼び出し後に `samp_windows_` を増やします。その後、関数内の `static const bool` として環境変数の有無を初回評価し、設定ありの場合に限って呼び出し回数が 200 の倍数となるたび次の行を stderr に出します（`metal/src/engine/window.cpp:3222-3227`）。

```text
strata metal: sampler <累計回数> windows, last <直近の行数> rows in <経過時間> ms
```

`windows` の回数は `Window` インスタンスの `samp_windows_` に保持されます（初期値 0、同 `metal/src/engine/window.cpp:338-345`）。環境変数の判定値は関数ローカル static なので、プロセス内で最初に `sample_run()` がここまで到達した時点で固定されます。以後に環境を書き換えても再判定されず、Window の再生成でも再評価されません。ログの時間は `run_graph()` 前後の `now_ms()` の差です。GPU 単体の実行時間だとはこのコードから確認できません。

## 根拠

- 全参照と判定、graph 実行、計数、stderr 出力: `metal/src/engine/window.cpp:3222-3227`。
- サンプラー呼び出し経路: `metal/src/engine/window.cpp:3145-3156,3291-3303`; Verifier の sampler 設定: `src/core/verify.cpp:3240-3250,4666-4676`。
- Metal build 条件: `metal/CMakeLists.txt:16-18,51-55,73-76`。
- `docs/DETAILS.md` と Metal docs 内に、この環境変数の説明や sampler 計測値は見つかりませんでした。索引候補 `docs/envvars/000_envvers.md:1457` に対し、読み取り実装は上記の Metal sampler 診断だけです。
