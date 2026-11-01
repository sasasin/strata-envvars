# `CUDA_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 自身がこの変数を読む主な箇所は、ネイティブ engine の `--gpu` 起動処理と、serve の GPU 選択・子プロセス環境の処理です。serve は設定の `gpu`（または GPU roles）から選択値を作ってエンジンに渡し、未選択なら親プロセスの環境値を引き継ぎます。`--gpu` を指定したネイティブ engine は最初の CUDA 呼び出しより前に環境値を上書きします。

この変数は Strata 固有の計算設定ではありません。CUDA runtime が列挙するデバイス数の記述にも現れますが、その列挙時の意味は外部 runtime の動作なので、ここでは扱いません（`include/strata/core/device.hpp:41-44`）。

## 値と判定

| 経路 | 未設定・空文字 | 設定値の処理 |
|---|---|---|
| ネイティブ engine の `--gpu LIST` | 未設定または空文字なら上書き警告なし。空文字以外の既存値が CLI 値と異なる場合は警告 | CLI の `LIST` を文字列として `CUDA_VISIBLE_DEVICES` に設定する。Strata は値の数値 parse や範囲検査をしない。HIP build では代わりに `HIP_VISIBLE_DEVICES` を設定する |
| `serve/server.py` の GPU 選択 | config で GPU を指定しない場合は親環境の値を辞書コピーで継承 | config の GPU 番号をカンマ区切りにして設定する。すべての GPU を Off にした場合は空文字を設定する。続く config の `env` が同じキーを指定すれば、その文字列で上書きする |
| serve の可視 GPU 対応付け | 値がない、空、または形式不一致なら対応付けなし | `CUDA_DEVICE_ORDER=PCI_BUS_ID` の場合に限り、`0`〜`99999` の1〜16個の整数をカンマ区切りにした文字列を受け付ける。値全体を正規表現で検査し、65535超または重複番号があれば対応付けなし |
| serve のカード案内ログ | 空要素を除いて分割し、空または連番 `0,1,...` なら案内を出さない | `gpu` 選択時に分割した番号が連番と異なる場合、選択 GPU とエンジン内の `GPU 0 / CUDA0` 等の対応を標準出力へ表示する。この箇所は番号の妥当性を検査しない |

ネイティブ `--gpu` の警告は `getenv` が null かどうかと、非空値が CLI 引数と異なるかだけで決まります。したがって `"0"` は CLI 値が別なら警告対象ですが、空文字は警告対象になりません。CLI 値そのものはこの処理で検証されず、後続の実行時エラーを Strata が事前に判定するコードは確認できません。

## 有効になる条件

- ネイティブ engine は `--gpu LIST` がある場合に限り、CUDA build では `CUDA_VISIBLE_DEVICES` と `CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定します。HIP build では変数名が `HIP_VISIBLE_DEVICES` に切り替わります。環境値だけを engine が読み取って別の Strata 内部設定に変換する処理ではありません（`src/program/generate.cpp:2957-2978`）。
- serve の engine 起動では `child_env()` が親環境をコピーし、選択 GPU がある場合に可視デバイスを設定します。GPU 番号は `gpu` 設定または保存済み GPU roles から決まり、CUDA の選択時は `CUDA_DEVICE_ORDER=PCI_BUS_ID` も設定されます。config の `env` はこの選択値より後に適用されるため、明示した `env.CUDA_VISIBLE_DEVICES` が最終値になります（`serve/server.py:3081-3095,3517-3528,3747-3763`）。
- 全カード Off の場合、serve は CUDA と HIP の可視変数を空文字にします。ただし同じ config の `env` が後から上書きできます。CUDA/HIP/SYCL engine で全カード Off を指定すると、起動処理は GPU に触れる前に `SystemExit` で停止します（`serve/server.py:3103-3121,3750-3760`）。
- NVIDIA GPU の速度情報を取る serve 補助 subprocess は、全カードの情報を得るためコピーした環境から `CUDA_VISIBLE_DEVICES` を削除して起動します。親プロセスや後続 engine の環境は変更しません（`serve/server.py:3407-3435`; 同じ処理は `strata_control/gpu_roles.py:432-454` にあります）。
- 画像生成の `image_env()` は親環境をコピーし、画像設定に `gpu` があり backend が `cuda` の場合にこの変数を設定して PCI order を指定します。config の `env` が最後に適用されます。画像プロセス起動に渡されます（`serve/images.py:131-150,221-239`）。
- Vision encoder の個別 GPU 設定 `vision.cuda_device` があれば、serve はコピーした環境の `CUDA_VISIBLE_DEVICES` をその番号に置き換えて vision 子プロセスへ渡します。設定がなければ engine 環境をそのまま使います（`serve/server.py:3931-3946,9202-9224`）。

## 実行時の詳細

ネイティブ engine は起動時、CUDA 呼び出しより前に argv の `--gpu` を走査します。最初に見つかった引数について、現在の可視変数が非空で CLI 値と異なるとき、stderr に `warning: --gpu %s overrides %s=%s from the environment` を出し、`CUDA_DEVICE_ORDER` を `PCI_BUS_ID`、可視デバイスを CLI 値に設定して走査を終えます。その後の option parse では `--gpu` の値を消費するだけです。環境値はこの時点で一度調べられます（`src/program/generate.cpp:2957-2978,3011`）。

serve の可視デバイス対応付け `visible_device_order()` は、backend が `None` または `cuda` であり、さらに `CUDA_DEVICE_ORDER` が厳密に `PCI_BUS_ID` の場合にだけ CUDA 変数を読みます。値が上記の形式に合わない場合、status 上の GPU ordinal と OS GPU index の対応を空として扱います。HIP backend は `HIP_VISIBLE_DEVICES` を使います（`serve/server.py:933-945`; serve status での呼び出し `serve/server.py:9458`）。

`card_note()` は config で GPU を選んだ CUDA 系経路で、環境辞書の値をカンマ分割して案内行を作ります。単一 GPU なら `[strata] running on GPU N ...`、複数 GPU なら stage 順の行を標準出力へ出します。連番なら表示しません（`serve/server.py:3865-3878,9193,9227-9230`）。

この変数を理由として Strata が終了する経路は特定できませんでした。serve の全カード Off エラーは GPU roles/config に対するチェックであり、環境値の parse エラーではありません。peer device が列挙数の外にあるときは `src/core/peer_experts.cpp:125-134` が `peer experts: CUDA device ... is not visible (... devices; set CUDA_VISIBLE_DEVICES)` というエラー文字列を返しますが、CUDA の列挙数や変数値の解釈自体は Strata のこの箇所では行っていません。

## 根拠

- 環境変数候補一覧: `docs/envvars/000_envvers.md:92`（調査文書リポジトリ）。
- ネイティブ engine の CLI 上書きと警告: `src/program/generate.cpp:937-939,2957-2978,3011`。
- serve の GPU 設定・継承・子環境: `serve/server.py:3081-3121,3517-3528,3747-3790`。
- serve の厳密な ordinal 対応付けとカード案内: `serve/server.py:933-945,3865-3878`。
- 画像／vision 子プロセスへの設定: `serve/images.py:131-150,221-239`; `serve/server.py:3931-3946,9202-9224`。
- 全 GPU 情報取得時の可視値削除: `serve/server.py:3407-3435`; `strata_control/gpu_roles.py:432-454`。
- peer device エラー文字列: `src/core/peer_experts.cpp:125-134`。
