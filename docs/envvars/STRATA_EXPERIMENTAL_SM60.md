# `STRATA_EXPERIMENTAL_SM60`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

これはエンジン実行時の GPU カーネルを直接切り替える変数ではなく、`setup.py` が Pascal / Volta 世代の NVIDIA GPU（アーキテクチャ番号 60〜70）を利用可能として扱うための opt-in です。該当 GPU が検出されたとき、値が有効ならセットアップが CUDA 12 の実験的エンジンを選べるようにし、必要な場合はそのビルドを取得またはコンパイルします。対応 GPU がない場合、この変数だけではエンジンや設定を切り替えません（`setup.py:1653-1661,1684-1701,1743-1761`）。

同じ名前は CMake の `STRATA_EXPERIMENTAL_SM60` ビルドオプションおよび C++ の compile definition にも使われますが、これはプロセス環境から読み取る変数ではありません。`setup.py` が環境変数を判定した後、アーキテクチャが sm_75 未満または toolkit が CUDA 12 のときに `-DSTRATA_EXPERIMENTAL_SM60=ON` を CMake に渡します（`setup.py:5873-5876,5944-5950`）。

## 値と判定

`setup.py` は `os.environ.get(..., "").strip() == "1"` で完全一致を判定します。数値変換や先頭文字判定はしません。

| 環境値 | 判定 |
| --- | --- |
| 未設定、空文字 | 無効 |
| `1`（前後に空白があっても可） | 有効 |
| `0`, `01`, `1x`, `true` など、それ以外 | 無効 |

この判定が有効でも、GPU の検出結果にアーキテクチャ番号 60〜70 のカードがなければ `old_gpus_opt_in()` は理由を返さず、古い NVIDIA GPU 向けの選択は起きません（`setup.py:1653-1657,1684-1693`）。sm_52 など 50〜59 の Maxwell はこの環境変数による対象に含まれません（`setup.py:1660-1666,1786-1792`）。

## 有効になる条件

- セットアップで NVIDIA GPU を検出し、そのうち少なくとも一枚のアーキテクチャ番号が 60〜70 であること。
- CUDA 13 では Pascal / Volta のコードをコンパイルできないため、対象 GPU を使うモデルは原則として CUDA 12 のエンジン経路になります。セットアップは該当 GPU を利用可能と判定し、`OLD_GPUS` に理由を保持します（`setup.py:1650-1657,1743-1761,9361-9369`）。
- `--backend hip` を選んだ場合は NVIDIA 用の警告を出さず、AMD/HIP の経路へ進みます（`setup.py:9365-9373`）。この環境変数は HIP 用エンジンのビルド指定ではありません。
- 既存モデルの起動時に古い GPU が選ばれ、設定済みエンジンが CUDA 13 なら `ensure_engine_for()` が CUDA 12 エンジンへ移します。対象エンジンが存在しない場合は取得またはビルドへ進み、CUDA 12 をコンパイルできる toolkit がなければセットアップは理由を示して失敗します（`setup.py:7575-7599,7606-7644,5660-5677`）。

## 実行時の詳細

### 優先順位と選択

GPU の利用理由を決める `old_gpus_opt_in()` は、対象 GPU が見つかった後、次の順で判定します。

1. `STRATA_EXPERIMENTAL_SM60` が空白除去後に `1` なら、その値を opt-in の理由にします。
2. そうでなければ `--cuda 12`。
3. そうでなければ `--gpu` / `--gpus` で対象 GPU が明示選択されている場合。
4. そうでなければ、利用可能な AMD GPU がなく、CUDA 13 対応 NVIDIA GPU もない場合は、対象 GPU だけがある PC として自動的に許可します。
5. それ以外では理由を返さず、たとえば新しい NVIDIA GPU がある PC では対象 GPU を自動選択しません（`setup.py:1684-1701,9361-9369`）。

これは「古い GPU を使える候補として認める」判定です。実際のエンジン toolkit は別に `cuda_choice()` が決め、`--cuda 13` は明示指定として優先されます。その場合、CUDA 13 に対象 GPU のコードがない旨を理由文字列に含めます。`--cuda 12` は対象 GPU の有無にかかわらずそのモデルに CUDA 12 を選びます（`setup.py:1743-1761`）。`STRATA_CUDA` は CLI `--cuda` の既定値として読まれるため、CLI 指定があればその値が使われます（`setup.py:9163-9166`）。

### ビルドと記録される結果

セットアップで対象 GPU を選ぶと、対象 GPU 向けの CUDA 12 エンジンを用います。Windows では適合する ready-made CUDA 12 エンジンが使われる場合があり、Linux、`--build`、または適合する配布エンジンがない場合はソースからビルドします（`setup.py:7606-7614`）。ローカルビルドでは `engine_defs()` が `-DSTRATA_EXPERIMENTAL_SM60=ON` を加え、CMake は CUDA ビルドにおいてこのオプションを compile definition にします（`setup.py:5873-5876,5944-5950`; `CMakeLists.txt:236,280-285`）。CMake はこの定義がない状態で sm_75 未満を指定すると構成を失敗させます（`CMakeLists.txt:251-265`）。

セットアップ時に opt-in が記録されると、通常は `older NVIDIA GPUs (Pascal / Volta) can be used (<理由>): experimental, through a second engine built with CUDA 12 ...` の警告が出ます。HIP backend のときはこの警告を抑えます（`setup.py:9365-9369`）。CUDA 12 のエンジンへ移行すると、セットアップは `sm_<番号> is older than CUDA 13 supports ... this model moves to the experimental CUDA 12 engine ...` の警告を出し、設定の `cuda` を 12 にして engine のパスを保存し、最後に engine の場所を表示します（`setup.py:7623-7644`）。

Python の読み取りは setup プロセス内の関数呼び出し時に行われ、C++ エンジン起動後に環境を変えてもビルド済みエンジンのコード有無は変わりません。`experimental_sm60()` と `old_gpus_opt_in()` 自体は呼び出し時に環境を読み直しますが、セットアップ処理は `OLD_GPUS` に opt-in 理由を保持します（`setup.py:1650-1657,1684-1693,9365-9369`）。

## 根拠

- 環境値を読む箇所と値判定: `setup.py:1653-1657,1684-1693`。
- GPU 世代の範囲、Maxwell との区別、利用可否: `setup.py:1660-1666,1786-1792`。
- 優先順位、`--cuda` 選択、既定値としての `STRATA_CUDA`: `setup.py:1684-1701,1743-1761,9163-9166`。
- セットアップ警告と起動時のエンジン移行: `setup.py:9361-9369,7575-7599,7623-7644`。
- ビルド指定と CMake オプション: `setup.py:5873-5876,5944-5950`; `CMakeLists.txt:236,251-265,280-285`。
- 説明資料との照合: `docs/OLDER_GPUS.md:62-88,102-119` は CUDA 12 エンジンへの経路と同名環境変数の opt-in を説明しており、セットアップコードと一致します。
