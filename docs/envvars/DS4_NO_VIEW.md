# `DS4_NO_VIEW`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DSV41 エンジンの GGUF モデルについて、モデル読み込み後に GGUF shard のメモリマップを解除し、ファイルから expert を読む経路へ切り替えます。変数名の「view」は GPU tensor view ではなく、モデルファイルの memory mapping を指します。値を読むのは `src/dsv41/ds4_model.cu` の `Model::Impl::load()` 内だけです。`rg` で候補名を検索すると、実際の読み取りは 3188、Windows HIP の既定判定は 3190、その他はコメント（1072、3186-3187）でした。動的な名前を渡す helper 経由の参照は見つかりませんでした。

## 値と判定

`getenv()` の有無と `std::atoi()` の結果で判定します。文字列全体の厳密な数値検証や範囲制限はありません。

| 環境値 | `atoi` の結果 | 明示指定時の判定 |
|---|---:|---|
| 未設定 | — | 通常のビルドでは無効。Windows HIP の統合 GPU では後述の自動判定へ |
| 空文字 | 0 | 無効。Windows HIP の自動判定も抑止 |
| `0`、`0tail`、数値で始まらない文字列 | 0 | 無効 |
| `1`、`1tail`、`2`、`-1`、` 1` | 非 0 | 有効 |

`atoi` は先頭の空白と符号を許し、先頭から読める十進整数を変換します。数値の後ろに文字があってもその部分は判定に使われません。数値として読めない文字列と空文字は 0 になります。別の環境変数や CLI オプションによる値の上書きはありません。`src/dsv41/ds4_main.cpp:1370-1378,1395-1410` に CLI 引数の解析とモデル読み込みがありますが、`DS4_NO_VIEW` を扱う CLI 引数はありません。

## 有効になる条件

- 明示値が `atoi(value) != 0` なら `no_view` が true になります。環境値が存在する限り、Windows HIP のハードウェア自動判定は行われません。したがって Windows HIP で `DS4_NO_VIEW=0` や空文字を指定すると、自動有効化を明示的に抑えます。
- `_WIN32 && STRATA_USE_HIP` のビルドで、変数が未設定かつ device 一覧が空でない場合だけ、先頭 GPU の `cudaGetDeviceProperties()` が成功し `integrated != 0` なら `no_view` を true にします。取得に失敗した場合は false のままです。
- どのビルドでも、実際に view を外す追加条件は `no_view && store && pk.gguf` です。GGUF でない pack、RAM store がない場合（容量が 0、対象形式でない等）、または判定が無効なら処理しません。RAM store の初期化条件は `src/dsv41/ds4_model.cu:5410-5413` にあります。
- Windows HIP 以外のビルドに、コード上の APU 自動既定はありません。環境値が未設定ならこの機能は無効です。

## 実行時の詳細

`DS4_NO_VIEW` はモデルごとの `load()` 中、store の初期化と preload の後に読み取られます。static cache はなく、モデルをロードするたびに評価されます。一度ロードしたモデルでは、その後の環境変更で既に解除した view を戻したり、判定を再実行したりしません。CLI の通常実行と `--serve` はどちらも `m.load()` 後に進みます。`--pack-info` はモデル読み込みより前に終了するため、この変数の判定に到達しません（`src/dsv41/ds4_main.cpp:1388-1410`）。

条件が成立すると `Pack::drop_views()` が各 shard の mapping を解除し、ファイル descriptor を開き直して `direct_reads` を有効にします。その後、RAM store に新しい buffered fallback descriptor を渡し、`views` 状態を false にします。stderr には次の行を出します。

```text
ds4: no view of the model's files after the load: unbuffered reads at the drive's rate
```

これは Strata が行う mapping 解除、descriptor の更新、ログ出力を示します。OS や driver が実際に達成する読み込み性能を保証するものではありません。該当処理は `src/dsv41/ds4_model.cu:3184-3201`、mapping と descriptor の更新は同ファイル `src/dsv41/ds4_model.cu:455-497`、store 側の fallback descriptor 更新は `src/dsv41/ds4_store.hpp:73-78` です。

mapping を解除した後、store slot を得られない expert は `StoreHold::rescue()` が `store->ensure()` で再取得を繰り返します。2000 回を超えても slot を得られない場合、stderr に `ds4: layer %d expert %d: no store slot and no view of the files` を出し、プロセスを終了コード 3 で終了します（`src/dsv41/ds4_model.cu:6777-6794`）。モデルの `load()` 自体がこれより前に失敗した場合は、呼び出し元が `maya-ds4: <error>` を stderr に出し、終了コード 1 を返します（`src/dsv41/ds4_main.cpp:1402-1407`）。

## 根拠

- 環境値の parse、Windows HIP の既定判定、適用条件、ログ: `src/dsv41/ds4_model.cu:3184-3201`。
- `views` 状態の初期値: `src/dsv41/ds4_model.cu:1069-1073`。
- GGUF 判定と shard mapping: `src/dsv41/ds4_model.cu:308-314,386-404`。
- file-backed expert の選択: `src/dsv41/ds4_model.cu:2255-2261`。
- store が作られる条件と fallback descriptor の更新: `src/dsv41/ds4_model.cu:5410-5413`、`src/dsv41/ds4_store.hpp:73-78`。
- mapping 解除後の expert 再取得と終了経路: `src/dsv41/ds4_model.cu:6777-6794`。
- DSV41 CLI / server 共通のモデルロード位置: `src/dsv41/ds4_main.cpp:1388-1410`。

`docs/DETAILS.md` と関連する Strix Halo / HIP ガイドに `DS4_NO_VIEW` の説明は見つかりませんでした。実装コメント `src/dsv41/ds4_model.cu:3186-3187` は Windows HIP の APU で既定 ON、decode +7.5%・prompt 変化なしと記しますが、同コメントには測定条件の詳細がなく、ここでは性能値を一般化しません。
