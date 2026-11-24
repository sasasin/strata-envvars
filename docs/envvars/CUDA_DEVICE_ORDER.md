# `CUDA_DEVICE_ORDER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Strata はこの変数を通常の設定値として読み込んで動作を切り替えるのではなく、CUDA の可視 GPU 番号を NVIDIA の PCI / `nvidia-smi` 順で扱う必要がある起動環境に `PCI_BUS_ID` を設定します。サーバーは CUDA の visible-device リストを物理 GPU 番号へ対応付けるとき、この値が正確に `PCI_BUS_ID` かを確認し、曖昧な場合は GPU 番号の対応付けを見送ります。Strata 内で確認できる効果は GPU 対応付けとその監視・split 候補の扱いであり、この値自体から生成計算や engine の指定 GPU リストを変える処理はありません。[`terminal/serve/server.py:4007-4028`](../../../../Niko1221/Strata/terminal/serve/server.py#L4007), [`terminal/serve/server_parts/engines.py:497-519`](../../../../Niko1221/Strata/terminal/serve/server_parts/engines.py#L497)

## 値と判定

Strata のサーバー側では、値を受け取った環境辞書と現在の環境から判定する箇所で比較方法が異なります。`visible_device_order` は文字列を正確に比較し、`gpu_roles.env_visible` は空白を除去して大文字化してから比較します。どちらも数値 parse はせず、`CUDA_DEVICE_ORDER` 自体に無効値エラーを出しません。

| 経路 | unset | 有効になる値 | 無効になる値と結果 |
|---|---|---|---|
| Serve の監視・helper GPU 対応付け (`visible_device_order`) | 環境辞書にない場合は空の順序。曖昧として物理番号への対応付けをしない | 完全一致の `PCI_BUS_ID` | 空文字、`pci_bus_id`、` PCI_BUS_ID `、`FASTEST_FIRST` などは不一致。visible-device 順序を返さず、監視 GPU は `0` に fallback し、helper GPU は追加されない |
| GPU role / split の既存環境可視範囲の解釈 (`env_visible`) | `os.environ`（引数 `environ` が省略時）にない場合は CUDA の順序を特定できない。`CUDA_VISIBLE_DEVICES` がない場合は可視範囲指定なし | `PCI_BUS_ID`。前後空白を除去し、大文字小文字を区別しないので `pci_bus_id`、` PCI_BUS_ID ` も受理 | 空文字、`FASTEST_FIRST` などは不一致。複数の異なる NVIDIA GPU があり、空でない `CUDA_VISIBLE_DEVICES` が設定されている場合、順序を曖昧として `None` を返す |
| Strata による子環境の設定 | `child_env` は親 `os.environ` のコピーを基礎にする。GPU が明示選択されない場合、元の値を維持 | `backend` が CUDA 相当で `gpu_list(cfg)` が空でない場合 `PCI_BUS_ID` を設定。vision の個別 `cuda_device` でも設定 | GPU 全 Off、SYCL 経路、HIP 可視 GPU 経路ではこの箇所からは設定しない。後続の config `env` または vision `env` が同じキーを指定すれば、その値で上書き |
| Engine の `--gpu LIST` | 該当 option がない場合はこの処理をしない | `--gpu` があると Windows は `_putenv_s`、その他は `setenv(..., 1)` で常に `PCI_BUS_ID` に上書き | 値の parse の対象ではなく、他の `CUDA_DEVICE_ORDER` 値があっても上書き |

根拠: [`terminal/serve/server_parts/engines.py:497-508`](../../../../Niko1221/Strata/terminal/serve/server_parts/engines.py#L497), [`terminal/strata_control/gpu_roles.py:485-510`](../../../../Niko1221/Strata/terminal/strata_control/gpu_roles.py#L485), [`terminal/serve/server.py:4010-4028,4141-4155`](../../../../Niko1221/Strata/terminal/serve/server.py#L4010), [`engine/src/program/generate.cpp:3784-3801`](../../../../Niko1221/Strata/engine/src/program/generate.cpp#L3784)

## 有効になる条件

- サーバーの `visible_device_order` がこの値を使うのは `backend` が `None` または `cuda` のときです。`hip` は HIP の visible-device 名を使い、その他の backend は空の順序を返します。[`terminal/serve/server_parts/engines.py:497-508`](../../../../Niko1221/Strata/terminal/serve/server_parts/engines.py#L497)
- Serve が子 engine の GPU を明示選択した場合（GPU がすべて Off のケースを除く CUDA 側の `gpu_list(cfg)` 経路）、`child_env` は環境をコピーして `PCI_BUS_ID` と `CUDA_VISIBLE_DEVICES` を設定します。ただし、後続の profile/config `env` が同じキーを指定するとその値を上書きします。[`terminal/serve/server.py:4007-4028`](../../../../Niko1221/Strata/terminal/serve/server.py#L4007)
- vision の `cuda_device` を個別指定した場合も CUDA 環境へ設定されますが、vision セクションの `env` はその後に適用され、上書きできます。[`terminal/serve/server.py:4141-4155`](../../../../Niko1221/Strata/terminal/serve/server.py#L4141)
- `--gpu LIST` を使う engine は CUDA/HIP の可視変数を CUDA 初回呼び出し前に上書きし、同時に `CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定します。HIP build は可視変数に `HIP_VISIBLE_DEVICES` を使いますが、同じ処理で order も設定します。[`engine/src/program/generate.cpp:3781-3801`](../../../../Niko1221/Strata/engine/src/program/generate.cpp#L3781)
- `gpu_roles.env_visible` では NVIDIA GPU が複数かつモデル/VRAM が同一でない場合に限って、順序不明の数値 `CUDA_VISIBLE_DEVICES` を曖昧とします。順序が同一機種間だけなら `alike=True` により order が不一致でも可視番号を解釈できます。順序が不明なままなら split の候補を既存環境から絞れず、全カードを候補に残します。[`terminal/strata_control/gpu_roles.py:485-510`](../../../../Niko1221/Strata/terminal/strata_control/gpu_roles.py#L485), [`terminal/strata_control/split_engine.py:396-405`](../../../../Niko1221/Strata/terminal/strata_control/split_engine.py#L396)

## 実行時の詳細

Serve の `child_env` は `os.environ` のコピーを作成し、その子 engine 用環境を起動箇所へ渡します。GPU 指定のない設定では親の値がコピーに残り、プロセス起動後に親の環境変数を変更しても既に作成された子環境辞書には反映されません。サーバーの GPU 対応付けは、engine 環境を作った後、監視 GPU と helper GPU を設定する際にその辞書を参照します。[`terminal/serve/server.py:4007-4028,9674-9694`](../../../../Niko1221/Strata/terminal/serve/server.py#L4007)

engine 自身は `--gpu` option を走査して CUDA 初回呼び出し前に環境を設定します。既存の可視 GPU 環境と指定値が異なるときは `warning: --gpu %s overrides %s=%s from the environment\n` を stderr に出します。この警告条件は `CUDA_VISIBLE_DEVICES`（HIP build では `HIP_VISIBLE_DEVICES`）の既存値に対するもので、`CUDA_DEVICE_ORDER` の値に対する警告ではありません。[`engine/src/program/generate.cpp:3781-3801`](../../../../Niko1221/Strata/engine/src/program/generate.cpp#L3781)

GPU role 判定で `environ` 引数がない場合は `os.environ` を読むため、同じ Python プロセス内で環境を変更すれば、その後の呼び出しは新しい値を参照します。`CUDA_DEVICE_ORDER` を保存する static cache はこの経路にはありません。[`terminal/strata_control/gpu_roles.py:485-510`](../../../../Niko1221/Strata/terminal/strata_control/gpu_roles.py#L485)

## ログと測定値

`CUDA_DEVICE_ORDER` の値が未設定・空・不一致であることを理由にした専用ログや終了経路はありません。Serve の `visible_device_order` は空リスト、`monitored_gpu` は `0`、`helper_gpus` は空リストに fallback します。`env_visible` は曖昧な場合 `None` を返し、呼出側の split 候補選択では可視カードを絞り込みません。[`terminal/serve/server_parts/engines.py:497-519`](../../../../Niko1221/Strata/terminal/strata_control/gpu_roles.py#L485), [`terminal/strata_control/split_engine.py:396-405`](../../../../Niko1221/Strata/terminal/strata_control/split_engine.py#L396)

## 根拠

- `terminal/serve/server.py:4007-4028,4134-4156,9674-9694` — Serve の環境コピー、CUDA 選択時の設定、vision 用設定、監視での利用。
- `terminal/serve/server_parts/engines.py:474-519` — visible order、監視 GPU、helper GPU の解釈。
- `terminal/strata_control/gpu_roles.py:485-510` — `os.environ` または明示環境辞書からの判定と曖昧ケース。
- `terminal/strata_control/split_engine.py:396-405` — `env_visible` の split 候補選択への影響。
- `engine/src/program/generate.cpp:3781-3801` — `--gpu` による初回 CUDA 呼び出し前の設定と可視 GPU 上書き警告。
