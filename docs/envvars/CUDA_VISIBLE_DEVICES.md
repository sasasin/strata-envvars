# `CUDA_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Strata の Python サーバーは起動環境を子 engine に引き継ぎ、GPU を設定で選んだ場合には engine 用の環境辞書にこの名前を設定する。全 GPU を Off にした場合は空文字を設定する。CUDA engine では `--gpu LIST` も CUDA 初期化前にこの値を書き換える。設定値は子 engine に渡すほか、GPU role の表示、split 対象の絞り込み、Monitor のカード対応付けにも使われる（`terminal/serve/server.py:4007-4028`、`engine/src/program/generate.cpp:3781-3802`、`terminal/strata_control/gpu_roles.py:485-510`、`terminal/strata_control/split_engine.py:396-405`、`terminal/serve/server_parts/engines.py:497-519`）。

Strata の所有コードには、通常の engine が起動環境からこの値を直接読み取って GPU を列挙・選択する処理はない。上記の C++ 読み取りは `--gpu` がある場合の既存値との比較だけで、実際の env 設定も同じ引数処理内で行う。環境変数による GPU 列挙の詳細は外部 CUDA runtime の処理なので、ここでは Strata が値を転送・解釈・設定する範囲を記す。

## 値と判定

Strata の各 Python 経路は同じ形式検査を共有しない。下表は Strata が環境辞書の値を読む箇所での規則であり、CUDA runtime 側の受理規則ではない。

| Strata の読み取り箇所 | unset | 値の扱い |
|---|---|---|
| `gpu_roles.env_visible`（GPU chooser の表示、split 候補） | `None`（可視カードを制限しない） | 空文字または空白だけは空リスト。カンマ区切りを各要素ごとに strip し、符号を除いた部分が数字か判定する。数値は `0 <= n < len(indexes)` の ordinal として `sorted(indexes)` からカードを引く。範囲外または負数で走査を打ち切る。UUID 等の非数値は `None`（絞り込めない）。重複は除去しない。NVIDIA で値が空でなく、カードが複数・異種で `CUDA_DEVICE_ORDER` が strip 後の大文字化で `PCI_BUS_ID` でない場合も `None` とする（`terminal/strata_control/gpu_roles.py:466-510`）。 |
| `visible_device_order`（Monitor / stage ordinal 対応） | `None` 以外の文字列が必要。未設定・空文字は `[]` | backend が `None` または `cuda` で、`CUDA_DEVICE_ORDER` が厳密に `PCI_BUS_ID` でなければ `[]`。値全体が `[0-9]{1,5}(,[0-9]{1,5}){0,15}` に一致し、各値が 0〜65535 かつ重複なしの場合だけ番号列を返す。空白、符号、UUID、16 個超、重複、範囲外は `[]`（`terminal/serve/server_parts/engines.py:497-508`）。 |
| `card_note`（起動時の補足表示） | `env.get(..., "")` として扱う | GPU が設定されている場合に文字列をカンマ分割し、各要素の前後空白を除去して空要素を落とすだけ。数値検証はしない。空、または `0,1,...` の順なら表示なし。それ以外は選択カードと engine 内 ordinal の対応を表示する（`terminal/serve/server_parts/engines.py:1105-1118`）。 |

環境値を engine に渡す経路では、Strata は一般の文字列値を検証・正規化しない。サーバーの `cfg["env"]` はキーと値を文字列化して設定し、後続の `--gpu` は値をそのまま設定する（`terminal/serve/server.py:4022-4028`、`engine/src/program/generate.cpp:3784-3802`）。

## 有効になる条件

- サーバーの `child_env` は現在の `os.environ` をコピーするため、GPU 選択を設定せず `cfg["env"]` にも同名キーがなければ、親プロセスの値が engine の子環境に残る。`cfg["env"]["CUDA_VISIBLE_DEVICES"]` があれば、server 側で自動設定した値を上書きする（`terminal/serve/server.py:4007-4028`）。
- `gpu_all_off(cfg)` の場合、backend にかかわらず `CUDA_VISIBLE_DEVICES` と `HIP_VISIBLE_DEVICES` を空文字にする。その後 `cfg["env"]` が同名キーを指定すれば再度上書きされる（`terminal/serve/server.py:4010-4028`）。
- `backend == "hip"` で HIP 側の GPU 選択がある場合、server は `HIP_VISIBLE_DEVICES` を設定し、CUDA 側の可視変数はこの分岐では設定しない。SYCL も `ZE_AFFINITY_MASK` 等を扱い、CUDA 側を設定しない（`terminal/serve/server.py:4017-4026`）。
- `backend` が HIP/SYCL でなく `gpu_list(cfg)` が空でない場合、server は `ordered_gpus(cfg)` をカンマ区切りにし、同時に `CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定する。設定内の `env` が後から両方を上書きできる（`terminal/serve/server.py:3915-3954,4007-4028`）。
- engine 起動引数に `--gpu LIST` があれば、CUDA build は CUDA 変数、`STRATA_USE_HIP` または `STRATA_HIP_GFX906` build は HIP 変数を `LIST` に設定し、`CUDA_DEVICE_ORDER=PCI_BUS_ID` も設定する。したがって engine 内では CLI の `--gpu` が起動時環境または server の設定値より後に適用される（`engine/src/program/generate.cpp:3781-3802`）。
- vision encoder は通常 engine の env を引き継ぐ。`vision.cuda_device` が指定されると CUDA backend では値を文字列化して CUDA 可視変数に設定し、`vision.env` がさらに上書きする。トップレベル `cfg["env"]` も引き継がれる（`terminal/serve/server.py:4134-4156,9411-9423`）。
- image generation の `image_env` は CUDA backend で設定 `gpu` を持つ場合にこの変数を設定する。リスト・タプルは各要素をカンマ結合し、単一値は `str()` 化する。その後、image 設定の `env` が上書きできる（`terminal/serve/images.py:177-196`）。
- vision の `strata-vision` と `strata-vision-own` は `--gpu` がない場合、CUDA 初期化等より前にこの変数を `-1` に設定する。`--gpu` がある場合はこの処理をしない（`terminal/tools/vision/strata_vision.cpp:97-107`、`terminal/tools/vision/own/own_main.cpp:31-41`）。
- NVIDIA GPU chooser と split planning は、環境値を数値 ordinal として読み取れないと絞り込みを行わない。Monitor の `visible_device_order` は CUDA backend で `CUDA_DEVICE_ORDER=PCI_BUS_ID` がない場合も対応付けを行わず、単一 GPU の既定番号 0 を使う（`terminal/strata_control/gpu_roles.py:485-510`、`terminal/strata_control/split_engine.py:396-405`、`terminal/serve/server_parts/engines.py:497-519`）。

## 実行時の詳細

server の `child_env` は呼び出し時に `dict(os.environ)` を作り、設定・分岐を加えた辞書を `StrataEngine` 等の subprocess に渡す。engine の通常起動では設定値を起動時に独自 cache する Strata 側コードは確認できなかった。子プロセス起動後に親環境を変えても、既に渡した子の env 辞書は変化しない（`terminal/serve/server.py:4007-4028,8820-8824,8850-8852,9391-9394`）。

engine の `--gpu` 上書きは CUDA 初期化より前に argv を走査して実行する。環境変数は存在有無だけでなく、既存値が非空かつ指定 LIST と異なる場合に警告する比較にも使う（`engine/src/program/generate.cpp:3781-3802`）。

GPU chooser の `env_visible` は呼び出し時に `os.environ`（または明示された `environ` 辞書）から読み、Monitor 用関数は server が構築した env 辞書を起動時に渡す。Strata 側にこの値を長期間保持する専用 cache はない（`terminal/strata_control/gpu_roles.py:485-510`、`terminal/serve/server.py:9674-9695`）。NVIDIA の速度情報を調べる補助 subprocess は、親環境のコピーから `CUDA_VISIBLE_DEVICES` を明示的に削除し、`CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定して起動する（`terminal/strata_control/gpu_roles.py:523-547`、同じ処理は `terminal/serve/server_parts/engines.py:959-980` にもある）。

## ログと測定値

- engine 起動時に既存値が非空で `--gpu` の値と異なると、stderr に `warning: --gpu %s overrides %s=%s from the environment` を出す。既存値が未設定・空、または指定値と一致する場合、この警告は出ない（`engine/src/program/generate.cpp:3784-3802`）。
- server は選択 GPU が一枚で ordinal 0 以外、または複数枚の順序が `0,1,...` でない場合、標準出力に `[strata] running on GPU ...` または `[strata] cards in stage order: ...` を出す。GPU 未選択、HIP backend、空値、既定 ordinal 順ではこの補足を出さない（`terminal/serve/server_parts/engines.py:1105-1118`、呼び出し `terminal/serve/server.py:9427-9429`）。
- `CUDA_VISIBLE_DEVICES` 自体の無効値に対する Strata engine の専用警告・エラーは見つからなかった。Python の補助的なカード対応付けで読めない値は曖昧または空の対応として扱う。性能測定値は記載しない。

## 根拠

- server の engine 子環境の継承・GPU 選択・設定 env の優先順位: `terminal/serve/server.py:4007-4028`
- server の vision 環境と engine 起動: `terminal/serve/server.py:4134-4156,9391-9423`
- `--gpu` による事前比較・上書き・警告: `engine/src/program/generate.cpp:3781-3802`
- 環境値の数値 ordinal 解釈と GPU chooser / split での利用: `terminal/strata_control/gpu_roles.py:466-510`、`terminal/strata_control/split_engine.py:396-405`
- Monitor 用 ordinal 解析とカード選択: `terminal/serve/server_parts/engines.py:497-519,1105-1118`、`terminal/serve/server.py:9674-9695`
- image generation 子環境と vision CPU モードでの設定: `terminal/serve/images.py:177-196`、`terminal/tools/vision/strata_vision.cpp:97-107`、`terminal/tools/vision/own/own_main.cpp:31-41`
- NVIDIA 速度調査 subprocess 用 env からの削除: `terminal/strata_control/gpu_roles.py:523-547`、`terminal/serve/server_parts/engines.py:959-980`
