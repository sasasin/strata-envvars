# `setup.py --gpu-roles`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`./setup.sh`、`START-HERE.bat` からも引数を転送） |
| オプション | `--gpu-roles` |
| 別名 | なし |
| 値 | `LIST`。GPU 番号と `main` / `helper` / `off` の組をカンマまたはセミコロンで列挙。区切りは `=` または `:` |

## 役割

GPU ごとの役割を指定し、`Main` を回答の最後の処理を担うカード、`Helper` をモデルの一部を保持するカード、`Off` を使用しないカードとして setup に選ばせます。役割はエンジンへ渡すカード順にも反映され、`Helper` を先、`Main` を最後に並べます。通常の CUDA/HIP setup でモデルを設定するときは、この役割をモデルの run config に保存します（`terminal/setup.py:11494-11495`、`terminal/setup.py:11652-11672`、`terminal/strata_control/gpu_roles.py:195-214`）。

## 使い方

```sh
# GPU 0 を Helper、GPU 1 を Main としてモデルを設定
./setup.sh --setup --family qwen --model IQ3_XXS --gpu-roles 1=main,0=helper --yes

# GPU 2 を Main、GPU 0 を Helper、GPU 1 は Off として指定
./setup.sh --setup --family qwen --model IQ3_XXS --gpu-roles '2:main;0:helper' --yes
```

GPU 番号は NVIDIA では `nvidia-smi` の番号、AMD では setup が列挙する番号です。`START-HERE.bat` も同じ option を `setup.py` に転送します（`terminal/setup.py:11489-11495`、`setup.sh:8-17,81`、`START-HERE.bat:53-63`）。

## 値と既定値

- 各要素は `GPU番号=役割` または `GPU番号:役割`。空白と役割名の大文字小文字は正規化されます。カンマとセミコロンは要素区切りです（`terminal/strata_control/gpu_roles.py:218-233`）。parser に明示的な空文字列を渡した場合は truthy 判定で role 解析を飛ばすため、未指定と同じ通常の GPU 選択経路になります（`terminal/setup.py:11652-11658`）。
- GPU 番号は 0 以上の十進数字で、同じ番号を二度指定できません。役割名は `main`、`helper`、`off` のみです。空の一覧もエラーです（同 `:228-238`）。
- `Main` は 1 枚までです。`Main` を省略した場合、通常の CUDA/HIP setup は指定された `Helper` のうち番号が最大のカードを `Main` にします（`terminal/setup.py:11661-11667`）。`Main` 以外に指定されなかったカードは `Off` です（同 `:11667`）。
- 少なくとも 1 枚を `Main` または `Helper` にする必要があります。全カードを `off` にする指定は setup で拒否されます（同 `:11661-11664`）。Intel app/Control の SYCL 経路では `roles_from_text` を通り、Main を省略すると有効な指定カード中で最速のカードが Main になります（`terminal/setup.py:9323-9334`、`terminal/strata_control/gpu_roles.py:247-252`）。
- 値を省略したときの既定値は parser にありません（値必須、`terminal/setup.py:11494-11495`）。この option を使わない場合は GPU 選択の通常経路になります。NVIDIA で複数カードを共有できるときは役割の推奨を表示して確認し、`--yes` なら推奨を採用します（同 `:2340-2361,2384-2419`）。

## 実行時の動作

通常経路では文字列を `gpu_roles.parse_roles` で解析し、`--gpu` または `--gpus` と併用すると parser error にします。解析した役割は、`Helper` の番号順の後ろに `Main` を置くカード列へ変換されます（`terminal/setup.py:11645-11672`、`terminal/strata_control/gpu_roles.py:195-200`）。

カード選択後、setup が作る run config には `gpu_roles` の番号別役割、互換用の `gpu`、および複数 GPU 時の `gpu_order: as_given` が書かれます。`setup_config` はモデル設定後の実際の GPU 列を使い、単一 GPU に縮退した場合も含めて役割を組み直します（`terminal/strata_control/setup_config.py:476-484,509-516`）。config は一時ファイルへ書いてから置き換えられ、既存 config の内容が変わる場合は `.bak` を作ろうとします（`terminal/setup.py:7531-7537,7715-7747`）。

`--gpu-roles` を `--setup` なしで既存モデルの起動に使った場合は、変換したカード列が `start()` に渡ります。通常の CUDA 起動ではその複数 GPU 選択が config の `gpu` と `layer_split` に保存されますが、この経路では `setup_config` の役割 map 書き込み処理を通りません（`terminal/setup.py:11725-11729,11761-11775,8558-8563,8640-8647`）。

Intel の app/Control SYCL 経路は通常の role 解析ブロックより先に `intel_control_setup` へ分岐し、`_select_sycl_cards` が `roles_from_text` でカードを選びます。source checkout の SYCL 経路は `setup_intel.py` に委譲し、同スクリプトが `setup.py` の `main()` を再利用します（`terminal/setup.py:11628-11638,9323-9348`、`engine/sycl/setup_intel.py:1-8,600-607`）。

## 適用条件と副作用

- 通常の CUDA/HIP setup では、指定した GPU 番号が現在の PC 上にあり、該当 backend で利用可能かを後続の GPU 選択処理が確認します。存在しない番号や利用不能カードは setup を止めます（`terminal/setup.py:2340-2361,2243-2269,5018-5049`）。
- モデルやメモリ条件により複数 GPU を使えない場合、setup は単一 GPU に縮退することがあります。明示的な `--gpu-roles` 指定では、縮退時に指定した `Main` を選びます（`terminal/setup.py:2364-2369,12104-12109`）。config の role map も最終的に残ったカード列に合わせられます（`terminal/strata_control/setup_config.py:509-516`）。
- 保存された役割は実行時のカード選択・順序として機能します。カードをオフにしたり役割を変えたりする GPU プロセス自体の作成・制御は、setup 後の server / engine 側の処理です。この文書ではその別経路の実行時挙動までは扱いません。

## 出力とエラー

- `--gpu` / `--gpus` との同時指定、書式不正、重複 GPU、複数 `Main`、有効なカードがゼロの場合は `ap.error(...)` で拒否します（`terminal/setup.py:11652-11667`、`terminal/strata_control/gpu_roles.py:225-243`）。
- 指定された番号が PC にない、または backend で使えない場合は setup の GPU 検査でエラーを表示して停止します（`terminal/setup.py:2243-2269,5018-5049`）。`fail()` は `[X]` のメッセージを出し、終了コード 1 で終了します（同 `:1049-1056`）。
- parser error の具体的な usage 表示と終了コードは Python `argparse` の処理です。Intel の委譲経路を含む全 platform での最終的な stderr 表示は、このソース調査では実行して確認していません。

## 根拠

- `terminal/setup.py:11489-11498` — `--gpu`、`--gpus`、`--gpu-roles` の parser 定義と値の説明。
- `terminal/setup.py:11628-11672` — platform/backend 分岐、相互排他、役割解析、Main 選定、GPU 選択への変換。
- `terminal/strata_control/gpu_roles.py:195-214,218-243` — Helper/Main の順序、config mirror、入力形式と validation。
- `terminal/setup.py:2340-2369,2384-2420,5018-5049` — 通常のカード選択、対話時の推奨、単一カードへの fallback、AMD 番号検査。
- `terminal/strata_control/setup_config.py:476-516` — 選択後の GPU と role map の config への反映。
- `terminal/setup.py:7531-7537,7715-7747` — run config の書き込みと既存 config の backup。
- `terminal/setup.py:11725-11729,11761-11775,8558-8563,8640-8647` — 既存モデル起動時に option の結果が渡る経路。
- `terminal/setup.py:9323-9348`、`engine/sycl/setup_intel.py:1-8,600-607` — SYCL の role 選択と source setup の委譲経路。
- `setup.sh:8-17,81`、`START-HERE.bat:53-63` — POSIX / Windows wrapper から `setup.py` への引数転送。
