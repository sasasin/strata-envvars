# `DS4_COPY_ALL`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 エンジンの GGUF モデルで、`--mmap-experts auto` 時に CPU 側の expert 全件を RAM にコピーする自動判定を上書きします。RAM が足りるという初期判定を強制できますが、コピー時にも容量を確認するため、実際の空き容量を超えてコピーする指定ではありません。

## 値と判定

`DS4_COPY_ALL` は `std::atoi()` の結果が非ゼロかどうかで判定します。文字列全体の検証はありません。

| 状態・値 | `cpu_lane_fits_ram()` の結果 |
| --- | --- |
| 未設定 | 通常の RAM 量・GPU 分担量による適合判定を行う |
| `0`、空文字、数値として 0 になる文字列（例: `false`, `junk`） | false。通常の適合判定へは戻らず、自動全件コピーを選ばない |
| 数値変換結果が非ゼロ（例: `1`, `-1`, `1tail`, ` 1`) かつ RAM 空き量が取得可能 | true。通常の適合判定を通さず、自動全件コピー候補にする |
| 数値変換結果が非ゼロでも RAM 空き量が不明 | false |

`atoi` は先頭の空白と符号を許し、数値以降の文字を検査しません。したがって `1tail` は非ゼロ、`0tail` はゼロとして扱われます。数値として読めない文字列と空文字は 0 です。オーバーフロー時の値はこのコードで規定されません。

## 有効になる条件

- DeepSeek V4.1 エンジンが読み込む GGUF モデルである。
- `--mmap-experts` が auto（省略時を含む）である。`--mmap-experts on` と `off` はそれぞれ明示値となり、この自動判定を通らない。
- `--ssd-cache` が未指定の自動状態である。
- `DS4_STORE_GB` と `DS4_COPY_GB` がどちらも未設定である。これらは値の内容にかかわらず、設定されていれば自動全件コピー判定より優先される。
- `DS4_COPY_ALL` が設定されている場合、`atoi` が非ゼロで、RAM 空き量を取得できること。

未設定時は `copy_all_fits()` が CPU 側 expert の推定量を RAM 空き量、システム用余裕 `kRamMargin`、Windows では commit 可能量と照合します。変数を非ゼロで設定した場合はこの初期適合計算を飛ばします。ただし、GPU の重み確保後に `copy_experts()` が再計算するコピー可能量を全 expert が超えると、自動モードではコピー予算が 0 になり、expert はファイル上に残ります。

## 実行時の詳細

最初の `store_gb()` 呼び出しで、GGUF の自動 RAM 判定に入った場合に `DS4_COPY_ALL` を読みます。`store_gb()` の結果は関数内の `static` 変数にキャッシュされます。そのため、この判定の後にプロセス環境を変更しても再評価されません。変数が判定を通すと `auto_copy_all` が true になり、需要時 RAM store の代わりに CPU lane の expert 全件をロード時にコピーする経路が選択されます。

GPU メモリ確保後、コピー処理は OS の空き RAM から `kRamMargin` を引いた量と commit 可能量の小さい方を上限として再確認します。自動モードで全件が収まらない場合、stderr に `ds4: the CPU lane's experts (...) do not all fit ...: read in place from the model's files ...` を出し、ファイルから読む経路になります。収まる場合は `ds4: --mmap-experts auto: ... copied in at load, no demand store ...` を出します。変数自体が設定されていることを示す専用ログはありません。

## 文書との照合

`docs/DETAILS.md` は `--mmap-experts` の mapped / resident / RAM budget モードを説明していますが、`DS4_COPY_ALL` の記載はありません。ソースでは、GGUF の auto 経路で RAM が全件分あるかの初期判定だけをこの変数が上書きし、コピー直前の空き容量チェックは残ります。したがって、この変数を「RAM 容量を無視して全件コピーする設定」と解釈することはできません。ここでは静的なコード読解のみを行い、ビルド、実行、性能測定はしていません。

## 根拠

- `src/dsv41/ds4_model.cu:4578-4587` — GGUF、auto mmap、cache 指定の除外、`DS4_COPY_ALL` の `atoi` 判定と未設定時の通常適合判定。
- `src/dsv41/ds4_model.cu:4596-4611` — `store_gb()` の一度だけのキャッシュと `auto_copy_all` の設定。
- `src/dsv41/ds4_model.cu:4251-4295` — コピー対象、コピー上限の再確認、容量不足時のファイル読み込みへの fallback とログ。
- `src/dsv41/ds4_model.cu:4177-4184` — 重みロード後に `copy_experts()` を呼ぶ箇所。
- `src/dsv41/ds4_main.cpp:1239-1242` — `--mmap-experts` の `on` / `off` / auto の値。
- `docs/DETAILS.md:223-237` — 利用者向けの低 RAM モード説明との照合。
