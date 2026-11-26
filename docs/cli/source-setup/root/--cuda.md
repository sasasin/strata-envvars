# `--cuda`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `terminal/setup.py`（root。`setup.sh` / `START-HERE.bat` は引数を転送） |
| オプション | `--cuda` |
| 別名 | なし |
| 値 | `12`、`13`、`auto` のいずれか |

## 役割

NVIDIA GPU を使ってモデルをセットアップするとき、そのモデル用エンジンの CUDA toolkit 世代を選びます。`12` は実験的な CUDA 12 エンジン、`13` は CUDA 13 エンジン、`auto` は GPU 世代と driver に基づく自動選択です。選択はモデル単位で行われ、CUDA 12 の選択は後のセットアップでもモデル設定から引き継がれます（`terminal/setup.py:2133-2151,9833-9837,10002-10004,11716-11717`）。

## 使い方

```sh
# Linux: モデルのセットアップで CUDA 12 エンジンを選択する
./setup.sh --setup --cuda 12 --family qwen --model <モデルサイズ>

# Windows: CUDA 13 エンジンを明示する
START-HERE.bat --setup --cuda 13 --family qwen --model <モデルサイズ>

# 自動選択（未指定時と同じ選択規則）
./setup.sh --setup --cuda auto --family qwen --model <モデルサイズ>
```

`setup.sh` と `START-HERE.bat` は `terminal/setup.py` に引数を渡します（`setup.sh:6-18,80-81`; `START-HERE.bat:8-13,49-65`）。

## 値と既定値

- parser は値を必須とし、`12`、`13`、`auto` だけを受け付けます。未指定時は `STRATA_CUDA` の値があればそれを既定値にし、なければ `None` です（`terminal/setup.py:11546-11549`）。この `None` と明示値 `auto` は、選択関数では同じ自動選択になります（`terminal/setup.py:2133-2151`）。
- 自動選択では、対象モデルに使う GPU のうち最も古い compute capability が CUDA 13 の対象下限（sm_75）未満なら CUDA 12、そうでなく driver が CUDA 13 の基準（580）未満かつ CUDA 12 の最低互換線（Linux 525 / Windows 528）以上なら CUDA 12、それ以外は CUDA 13 です（`terminal/setup.py:287-299,2133-2151`）。
- 明示値 `12` はカード世代にかかわらず CUDA 12 を選びます。明示値 `13` は CUDA 13 を選び、古いカードに CUDA 13 のコードがない場合でも選択を拒否せず警告します（`terminal/setup.py:2133-2147`）。

## 実行時の動作

- 通常のセットアップでは NVIDIA GPU を選んだ後に `cuda_choice()` が toolkit を決めます。その値をエンジン取得・build に渡し、CUDA 12 なら ready-made engine の検索先を CUDA 12 に限定し、取得できない場合は CUDA 12 toolkit でローカル build します。CUDA 13 の場合は通常の CUDA 13 engine を検索・build します（`terminal/setup.py:11816,11894-11905,9597-9631`）。
- CUDA 12 build は `engine-cuda12/` と専用の build folder を使い、`STRATA_EXPERIMENTAL_SM60=ON` の build 定義を追加します（`terminal/setup.py:6902-6947,6870-6873`）。ready-made engine の利用時には CUDA runtime wheel も選択 toolkit に応じて準備します（`terminal/setup.py:9615-9619`）。
- CUDA 12 を選択すると、Pascal / Volta GPU の opt-in としても扱われ、該当 GPU が検出された場合は実験的サポートの警告を出します（`terminal/setup.py:2043-2047,2074-2091,11783-11791`）。
- 作成される通常モデルの run config は CUDA 12 の場合だけ `"cuda": 12` を保存します。Qwen3.6 own-path も同様です。再セットアップで明示指定がない場合、保存された CUDA 12 を再利用します。CUDA 13 は toolkit 指定を保存せず、既定の選択規則に戻ります（`terminal/strata_control/setup_config.py:433-437`; `terminal/setup.py:9999-10004,11701-11717`）。
- `--rollback-engine` と併用した場合は別用途で、値が `12` のとき `engine-cuda12/` の直前のエンジンを戻し、それ以外（未指定、`auto`、`13`）は `engine/` を対象にします（`terminal/setup.py:11692-11697,6258-6279`）。通常起動や `--update` の分岐はこの値を toolkit 選択へ使いません（`terminal/setup.py:11695-11698,11761-11766`）。

## 適用条件と副作用

- 主な選択処理は NVIDIA GPU のセットアップ経路にあります。AMD HIP は CUDA toolkit 選択を通らず、macOS と Intel SYCL はこの処理より前に別経路へ分岐します（`terminal/setup.py:11628-11638,11816-11818,11894`）。それらの経路で `--cuda` が同じ意味を持つことは確認できません。
- CUDA 12 は実験的です。driver は少なくとも CUDA 12 の互換最低線（Linux 525 / Windows 528）が必要で、さらに配布 engine package 固有のより高い driver floor を警告する場合があります。CUDA 13 の driver 基準は 580 です（`terminal/setup.py:287-299,11897-11905,2133-2151`）。
- 明示 `--cuda 13` と sm_75 未満のカードを組み合わせると、そのカード向けコードがなく実行できない旨を警告します。CUDA 12 を RTX 50（sm_120）向けに選ぶ場合も CUDA 12.8 build の長時間 prompt に関する警告があり、build には CUDA 12.8 以上が必要です（`terminal/setup.py:2139-2144,6611-6621`）。
- セットアップでは engine の取得やローカル build、runtime wheel の準備に加え、モデル設定ファイルと起動スクリプトを書きます。`--no-start` は最後のモデル起動を抑止しますが、セットアップ作業自体を取り消しません（`terminal/setup.py:9597-9631,10002-10004,10044-10059,7531-7537`）。

## 出力とエラー

- `--cuda` に値を付けない場合や、選択肢外の値を渡した場合は argparse の usage error になります（`terminal/setup.py:11546-11549`）。
- 選択した toolkit に対して driver が最低線を下回ると setup はエラー終了します。CUDA 12 の配布パッケージ固有 floor 未満は別途警告されます（`terminal/setup.py:11897-11905,2154-2160`）。
- `--cuda 13` が古い compute capability を含むモデルに選ばれたときは警告を出しますが、この関数自体は拒否しません。実際に実行できるかは選択された engine が対象 GPU 用コードを持つかにも依存します（`terminal/setup.py:2139-2147`）。

## 根拠

- `terminal/setup.py:11546-11549` — parser の値候補、`STRATA_CUDA` 既定値。
- `terminal/setup.py:2133-2151,287-299` — 自動選択、明示値の優先、GPU 世代・driver による選択基準。
- `terminal/setup.py:11816-11905` — GPU 選択後の適用、driver 判定と警告。
- `terminal/setup.py:9597-9631,6902-6947,6870-6873` — ready-made engine / local build への toolkit の伝播と CUDA 12 build の配置。
- `terminal/setup.py:2043-2047,2074-2091,11783-11791,6611-6621` — 古い GPU の opt-in、警告、CUDA 12 build 条件。
- `terminal/strata_control/setup_config.py:433-437`; `terminal/setup.py:9999-10004,11701-11717` — CUDA 12 選択の設定保存と再セットアップ時の引き継ぎ。
- `terminal/setup.py:11628-11638,11692-11698,6258-6279` — macOS / SYCL 分岐、rollback 時の別用途。
- `setup.sh:6-18,80-81`; `START-HERE.bat:8-13,49-65` — wrapper が引数を `setup.py` へ転送する箇所。
