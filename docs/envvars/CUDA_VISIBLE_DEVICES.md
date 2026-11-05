# `CUDA_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。外部ライブラリと GPU driver が読む動作は対象外。

## 役割

Strata の Python 側では、NVIDIA GPU の表示範囲を launch plan のカード一覧に反映し、server や画像生成子プロセスの環境へ GPU 選択を渡します。engine の C++ 起動処理は `--gpu LIST` がある場合に、その値を CUDA 初期化より前にこの変数へ設定します。engine は通常、親環境から継承した値を設定として parse しません。

値の意味を解釈して GPU を隠す外部 runtime / driver の挙動はここでは説明しません。Strata 自身が行う値の解釈は、launch UI のカード表示と server の topology 表示に限られます。

## 値と判定

| Strata の箇所 | 未設定 | 空文字 | 設定値・不正値 |
|---|---|---|---|
| `strata_control.gpu_roles.env_visible()` | `None` を返し、環境による絞り込みなしとして扱う | 空リスト `[]`（表示 GPU なし） | カンマ区切りの数値をカード index として解釈。各 token は前後空白を除去し、先頭の `-` をすべて除いた部分が数字かを確認する。非数字 token（UUID、`+1` など）があれば `None`。負数またはカード数以上の番号でリストを打ち切り、それまでの番号を返す。複数の `-` で始まる token は数字チェックを通るものの、後続の `int()` が `ValueError` になる。 |
| server の `visible_device_order()` | 空リスト `[]` | 空リスト `[]` | CUDA backend（または backend 未指定）かつ `CUDA_DEVICE_ORDER` が厳密に `PCI_BUS_ID` のときだけ読む。値は 1〜5 桁の数字を最大 16 個、カンマで連結した形式に限定。重複、各値が 65535 超、形式外は空リスト `[]` |
| C++ engine 起動時 | `--gpu` がなければ Strata はこの変数を変更しない | `--gpu ""` なら空文字を設定する。既存値が空なら上書き警告なし | `--gpu` の次の引数を文字列のまま設定し、環境変数としての parse / clamp はこの処理ではしない。既存値が非空かつ引数と異なる場合だけ stderr に警告 |

`env_visible()` の数値解釈は OS の環境値を変更しません。これは launch plan のカード列挙用です。CUDA のカード順と nvidia-smi の番号の対応を特定できない場合、値が非空でも `None` を返します。具体的には、異なる GPU が複数あり、`CUDA_DEVICE_ORDER` が trim 後の大文字化で `PCI_BUS_ID` でない場合です。同一モデル・同一メモリ容量のカード群では `alike=True` としてこの曖昧性チェックを省きます。

根拠: `strata_control/gpu_roles.py:434-476`; `serve/server.py:1023-1034`; `src/program/generate.cpp:3321-3342`。

## 有効になる条件

- **Launch UI / plan:** `strata launch --plan` のカード役割表示は `visible_cards()` を呼び、NVIDIA では現在の Strata プロセス環境の `CUDA_VISIBLE_DEVICES` を使って、環境が隠すカードを一覧から外します。ユーザーが `--gpu` / `--gpu-roles` で指定したカードは `keep` に含めるため一覧に残します。値を index に変換できず `None` になる場合は、全カードを残します。環境値が未設定の場合も全カードを残します。layer-split のカード候補も、カードを明示していないときは同じ helper で絞ります。
- **Strata server の engine 子プロセス:** `child_env()` はまず server の `os.environ` をコピーします。全 GPU が Off の場合は CUDA と HIP の両方を空文字にし、HIP backend で選択カードがある場合は HIP 変数を設定します。それ以外で config から GPU が選択されていれば `ordered_gpus(cfg)` をカンマ区切りにして `CUDA_VISIBLE_DEVICES` に設定し、`CUDA_DEVICE_ORDER=PCI_BUS_ID` も設定します。GPU 未指定なら継承値を保ちます。その後 config の `env` を適用するため、そこに `CUDA_VISIBLE_DEVICES` があれば先に選択した値や継承値を上書きします。
- **画像生成 / vision 子プロセス:** `serve/images.py` は backend が `cuda` で config に `gpu` がある場合、scalar を文字列化し、list / tuple はカンマ区切りにして変数へ設定し、`CUDA_DEVICE_ORDER=PCI_BUS_ID` にします。続く config `env` がその値を上書きできます。server の vision encoder も `vision.cuda_device` が指定されると encoder 用に値を単一 GPU 番号へ差し替えます。HIP backend は CUDA 変数ではなく HIP 変数を設定します。
- **C++ engine の CLI:** `--gpu LIST` が環境値より優先します。CUDA 初期化より前に `CUDA_DEVICE_ORDER=PCI_BUS_ID` と `CUDA_VISIBLE_DEVICES=LIST` を設定します。HIP build では同じ処理が `HIP_VISIBLE_DEVICES` を対象にします。`--gpu` がない場合、このコードは親環境の値を変更しません。
- **`strata-vision`:** GPU を使わないモードでは backend 初期化前に CUDA と HIP の両方を `-1` に設定します。`--gpu` を指定した場合、この設定分岐は通りません。

標準 server 起動では、GPU roles がすべて Off で、backend が CUDA / HIP / SYCL など GPU 必須の場合、engine を起動せず `[strata] every graphics card is set to Off, and this engine cannot start without one...` で終了します。CPU / Metal、または macOS では all-Off の説明を出して続行します。

根拠: `strata_cli/launch/cmd.py:475-493`; `strata_control/split_engine.py:366-375`; `serve/server.py:3553-3597,4325-4355`; `serve/images.py:142-161,251-258`; `serve/server.py:4509-4524,10117-10126`; `tools/vision/strata_vision.cpp:130-143`。

## 実行時の詳細

engine の起動処理は argv を走査し、最初の `--gpu` とその次の引数を見つけると、ビルドが HIP なら `HIP_VISIBLE_DEVICES`、それ以外なら `CUDA_VISIBLE_DEVICES` を対象にします。従って CUDA build では、既存値が非空で CLI 値と文字列として異なる場合に限り、stderr に `warning: --gpu <値> overrides CUDA_VISIBLE_DEVICES=<既存値> from the environment` を出します。既存値が空、未設定、または CLI 値と一致すると警告しません。Windows は `_putenv_s`、それ以外は上書きフラグ付き `setenv` で更新します。その後の引数 parse ループでも `--gpu` を消費しますが、値の判定はこの環境設定箇所で行わず、`--gpu` に値がなければ `--gpu needs a value` を stderr に出して status 2 で終了します。環境変数自体の設定時点は、ソースコメント上、最初の CUDA 呼び出しより前です。プロセス内での再読み取りや cache は Strata 所有ソースにはありません。

server の `visible_device_order()` は engine に渡す env dict から値を読み、engine ordinal と OS GPU index の対応が明確な場合だけ topology 表示用の順序を返します。返り値は topology の `device_index` 対応付けに使われ、env や engine の GPU 選択は変更しません。server 起動時の `card_note()` は CUDA backend かつ GPU 選択ありの場合に env dict の値を確認し、選択番号が `0,1,...` と一致しなければ、たとえば単一 GPU なら `[strata] running on GPU N (as nvidia-smi numbers it); the engine's log calls it GPU 0 / CUDA0` を stdout に出します。

GPU 性能スコアを取得する補助 subprocess では、Strata はコピーした環境から `CUDA_VISIBLE_DEVICES` を削除し、`CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定して NVIDIA driver API の全カード番号を問い合わせます。この処理は起動対象 engine の環境選択ではありません。取得に失敗した場合、server のスコア helper は `None`、GPU roles helper は `{}` を返します。

根拠: `src/program/generate.cpp:3321-3342,3368-3377`; `serve/server.py:1023-1034,3980-4008,4443-4457,8014-8027,10129-10132`; `strata_control/gpu_roles.py:489-519`。

## 文書との照合

`docs/MULTI_GPU.md` は `strata launch --gpu` / `--gpu-roles` でカードを選ぶ利用方法を説明しています。今回確認した `docs/DETAILS.md` に `CUDA_VISIBLE_DEVICES` 固有の値 parse や環境優先順位の説明はありません。上記の値規則と優先順位は現行ソースに基づきます。

根拠: `docs/MULTI_GPU.md:16-30`; `src/program/generate.cpp:3321-3342`; `serve/server.py:4325-4338`。
