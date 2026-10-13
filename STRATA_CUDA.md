# `STRATA_CUDA`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。対象は Strata 所有コード。外部 CUDA ライブラリや driver の環境変数動作は含めない。

## 役割

`setup.py` が NVIDIA GPU 用モデルエンジンを準備するときに、CUDA 12 または CUDA 13 のエンジンを選ぶ設定です。エンジン選択はモデル単位で、選んだ GPU の compute capability に応じてビルド対象を決めます。実行中の CUDA ランタイムがこの環境変数を読む実装は見つかりませんでした。

## 値と判定

`argparse` の `--cuda` オプションの既定値として `os.environ.get("STRATA_CUDA") or None` を使います。環境変数から得た文字列を数値には変換せず、`cuda_choice()` が文字列全体を `"12"` / `"13"` と比較します。

| 設定 | NVIDIA のモデルセットアップ時の選択 |
|---|---|
| 未設定または空文字 | 自動選択。全 GPU が CUDA 13 対応なら CUDA 13、Pascal / Volta を含むなら CUDA 12 |
| `12` | GPU 世代にかかわらず CUDA 12 エンジンを選ぶ |
| `13` | GPU 世代にかかわらず CUDA 13 エンジンを選ぶ。Pascal / Volta があれば、そのカード用コードがなくエンジンが動かない旨の警告理由が付く |
| `auto` | 自動選択 |
| その他の文字列（例: `12x`, ` 12`） | `cuda_choice()` では `12` / `13` のどちらとも一致せず、自動選択と同じ扱い |

環境変数値は `argparse` のオプション既定値として渡されるため、CLI の選択肢検査はコマンドラインで `--cuda` を指定した場合に適用されます。`--cuda` を明示した場合はその値が環境変数由来の既定値を置き換えます。CLI では `12`、`13`、`auto` 以外は引数エラーになります。

## 有効になる条件

- CUDA 選択は NVIDIA 側のモデルエンジン選択経路で行います。AMD HIP の経路では `cuda_tk` は初期値 13 のままで、この選択値を HIP エンジンのビルドには渡しません。Intel SYCL は `--backend sycl` の処理へ分岐します。
- 自動選択は選んだ GPU 群の最小 compute capability で決まります。CUDA 13 が対象にできない Pascal / Volta（sm_60〜sm_70）が含まれる場合は CUDA 12、それ以外は CUDA 13 です。
- `12` / `13` の強制選択はサポート可否の拒否ではありません。CUDA 13 を Pascal / Volta に強制すると、コードがない旨を警告理由に含めます。`--cuda 12` は古い GPU 以外にも適用できます。
- `STRATA_EXPERIMENTAL_SM60`、GPU の明示選択、GPU 構成も旧世代 GPU の利用可否に関係しますが、これらは別の判定です。`STRATA_CUDA=12` は `old_gpus_opt_in()` にも `cuda` 引数として渡り、Pascal / Volta の opt-in 理由になります。新しい NVIDIA GPU が同居するだけでは旧 GPU を自動選択しません。
- 保存済みモデルを既存設定から再構成するときは、環境値を指定しない場合に設定中の CUDA 12 を引き継ぐ処理があります（`setup.py:4944-4945`）。新しいモデルのセットアップや明示的な再セットアップでは、環境値または `--cuda` による選択が使われます。

## 実行時の詳細

`STRATA_CUDA` は `setup.py` の引数定義時に読み取られます。その後 NVIDIA 経路で `cuda_choice(gpu["archs"], a.cuda)` が CUDA toolkit を決め、必要に応じて CUDA 12 用の既製エンジンを取得するか、`build_engine(..., toolkit=cuda_tk)` に選択値を渡します。既製エンジンを使うときも toolkit に対応する CUDA ライブラリの準備を行います。CUDA 12 が選ばれたモデルの設定には `"cuda": 12` が保存され、以降の起動・更新でそのエンジンを識別します。

セットアップ時には `CUDA 12: ...` / `CUDA 13: ...` の選択理由や、必要な driver が古い場合の停止メッセージが出ます。CUDA 12 は `engine-cuda12/`、CUDA 13 は通常の `engine/` を使います。`--rollback-engine` の場合も `a.cuda == "12"` のときだけ CUDA 12 側へ戻し、それ以外は CUDA 13 側を指定します。

読み取りは Python プロセス内で引数を定義するときの一度です。後から環境変数を変更しても、そのプロセスの `a.cuda` は再評価されません。通常のモデル起動時に実行エンジンが `STRATA_CUDA` を直接参照する箇所はありません。

## 根拠

- `setup.py:4853-4856`: 環境変数を `--cuda` の既定値に設定し、CLI の選択肢と説明を定義。
- `setup.py:936-953`: CUDA 12 指定を Pascal / Volta の opt-in 根拠に使用。
- `setup.py:966-981`: `12` / `13` の完全一致と、未指定・その他の自動選択規則。
- `setup.py:4944-4945,5017-5019,5083-5095`: 保存済み設定の引き継ぎ、HIP の初期値、NVIDIA での CUDA 選択と driver 条件。
- `setup.py:5446-5456,5461,5685-5689`: 既製エンジン取得・ビルド・ライブラリ選択と、CUDA 12 選択のモデル設定への保存。
- `setup.py:4920`: rollback では `a.cuda` が文字列 `12` の場合だけ CUDA 12 を選択。
- `docs/OLDER_GPUS.md:36-63`: CUDA 12 / 13 エンジン、旧 GPU の選択条件、`STRATA_CUDA=12` の説明。ソース実装と一致する説明として参照。
