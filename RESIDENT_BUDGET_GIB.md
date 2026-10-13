# `RESIDENT_BUDGET_GIB`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有の Docker 起動スクリプト、セットアップコード、エンジンコード。外部ライブラリの環境変数は対象外。

## 役割

Strata の Docker 起動スクリプトがセットアップ時に読む設定です。対象モデルでは、GPU の expert cache に入らない expert のうち、指定した GiB 分を RAM に保持する予算として `setup.py --resident-budget-gib N` に渡します。残りの expert はモデルファイルから読みます。これはエンジンの `--resident-budget-gib` オプションを構成するための Docker 用入力で、エンジンが `RESIDENT_BUDGET_GIB` 自体を読む実装は見つかりませんでした。

## 値と判定

| Docker 環境変数 | 起動スクリプトでの扱い |
|---|---|
| 未設定または空文字 | `${RESIDENT_BUDGET_GIB:-}` により空になり、CLI 引数を追加しない。setup.py がモデルと RAM から予算を選ぶ。 |
| 空でない値 | 空白除去や shell 側の数値検査をせず、その文字列を `--resident-budget-gib` の引数として渡す。 |

setup.py は引数を Python `float` として解析し、`N > 0` でなければ argparse のエラー `--resident-budget-gib takes a number of GiB above 0, e.g. --resident-budget-gib 32` で終了します。0、負値、数値に変換できない文字列は受け付けません。通常の正の小数値も指定できます。NaN は `N > 0` を満たさないため拒否されます。正の無限大はこの比較を通り、上限検査もありませんが、エンジンは GiB を byte 数に変換して整数にするため、整数の表現範囲を超える値の結果は保証されません。極小の正値もエンジンで byte 数へ切り捨てられ、0 になり得ます。明示値を推奨値より大きくしてもセットアップはその値を保持し、RAM 不足のリスクを警告します。通常の有限値について、実際に保持できる量はエンジン側で利用可能 RAM に合わせて制限されます。

## 有効になる条件

- `docker-entrypoint.sh` がセットアップを実行する場合に限り、環境変数が CLI 引数へ反映されます。`REINSTALL=1` または対象モデルの設定ファイルがまだない初回起動がこの経路です。設定ファイルがすでにあり再セットアップしない起動では、環境変数はセットアップに渡されず、保存済み設定が使われます。変更を反映するには `REINSTALL=1` が必要です。
- setup.py で予算が適用される対象は `UD-Q4_K_XL` と `UD-IQ4_XS` です。それ以外のモデルでは警告を出し、設定値はモデルの expert 配置に使いません。
- 複数 GPU の layer split はエンジン世代と setup の分岐によって扱いが変わります。budget 対応 split でない複数 GPU 構成では setup が単一 GPU に切り替える場合があり、予算引数を生成しない split 経路もあります。
- Dockerfile は NVIDIA CUDA イメージを使います。この環境変数を導入する起動経路は `docker-entrypoint.sh` です。通常の setup CLI は同名の環境変数を直接読みません。

## 実行時の詳細

`docker-entrypoint.sh` は値が空でなければ、セットアップ引数に `--resident-budget-gib "$RESIDENT_BUDGET_GIB"` を追加します。setup.py は通常、UD-Q4_K_XL / UD-IQ4_XS の expert 総量、ホスト RAM、KV streaming の RAM 使用量などから推奨値を作ります。明示値があればそれを優先し、指定値が推奨値より大きい場合は OS・エンジン・ファイル cache の余裕が減るリスクを警告します。

セットアップは最終的な値を生成エンジンの設定引数 `--resident-budget-gib N` として保存します。KV streaming が有効で予算が自動選択だった場合は、KV cache の RAM 分を差し引いて予算を再計算します。明示予算は自動で差し引かず、KV cache が別途 RAM を使うことを通知します。engine option は `atof` で数値化され、正値をバイト数へ換算します。同時に mmap と RAM 上の expert 保持を有効にし、RAM 予算の tier では頻度の高い GPU 非常駐 expert を RAM に保持し、残りをモデルファイルから読みます。予算を確保できない場合は警告を出し、GPU に保持されない expert をファイルから読む fallback になります。

エンジン起動時の stderr には `experts via mmap (--mmap-experts; ...)` と、file tier の読み方が表示されます。RAM tier を確保できた場合は `resident RAM mode: ... GiB of experts in RAM ...`、確保できない場合は `WARNING: the RAM budget (--resident-budget-gib) cannot be kept (...)` を出します。エンジン内部には `STRATA_RESIDENT_PIN` と `STRATA_RESIDENT_HEADROOM_GIB` による関連調整もありますが、これらは別変数であり、本ファイルの主役ではありません。

## 根拠

- `docker-entrypoint.sh:33,70-86` は値を空文字既定で取り込み、初回セットアップまたは `REINSTALL=1` の場合に限り、非空値を `--resident-budget-gib` に渡します。`docker-entrypoint.sh:90-106` は既存設定を使って通常起動する経路です。
- `setup.py:4910-4912,4938-4939` は引数を float として定義し、正値を要求します。
- `setup.py:1651-1656,1675-1686` は自動推奨値の RAM 計算と、指定値を保持する処理、推奨値超過時の警告を定義します。
- `setup.py:5274-5292` は対象モデルの budget 選択と非対象モデルの警告を示します。
- `setup.py:5667-5682` は KV streaming との相互作用と、config に保存する engine 引数を示します。複数 GPU の split 制約は `setup.py:3591-3631` にあります。
- `src/program/generate.cpp:2161-2170` は engine 引数の変換、実行モードの設定、正値チェックを示します。`src/program/generate.cpp:4671-4703,6848-6865` は mmap/file tier、RAM 保持結果、失敗時 fallback のログを示します。
- `docs/DETAILS.md:247-258` は予算モードの設計説明と測定例を記載しています。測定例は資料記載の UD-Q4_K_XL、64 GB PC、N=40、RTX 5070 の条件に限られ、一般的な性能保証としては扱いません。
