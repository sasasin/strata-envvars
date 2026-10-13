# `STRATA_STAGER_SSD`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。調査対象リポジトリの作業ツリーは clean。外部ライブラリの環境変数は対象外。

## 役割

CUDA prompt stager が、ファイルから一時的に取り出す expert blob をコピーする際に使う「SSD 向け」プロファイルを強制します。プロファイルが選ばれると、`STRATA_STAGER_THREADS` が未設定の場合は最大 32 スレッドを使い、ring 深度も別途指定されていなければスレッド数の4倍にします。選ばれない場合、スレッド数は CPU 論理数に応じた2～4、ring 深度は既定16です。

通常は Linux で file-backed source のページキャッシュを調べ、キャッシュ済みページが少ないときに SSD 向けプロファイルを選びます。この変数はその自動判定を上書きします。対象は実行時の CUDA prompt staging で、ビルド設定や decode の staging ではありません。

## 値と判定

環境変数を読むのは `Prefill::init()` が stager を初期化するときだけです。`STRATA_STAGER_THREADS` が未設定で、かつ source に transient blob がある場合に限り、この変数を確認します。

| 状態 | `files`（SSD 向けプロファイル）の扱い |
|---|---|
| unset | `src->cached_share(256)` を呼ぶ。戻り値が `0.9` 以上なら RAM 向けにし、それ未満なら SSD 向けのままにする。`-1`（判定不能）も RAM 向け条件を満たさないため SSD 向けのまま。 |
| 空文字 | 強制値として扱わず、unset と同じ自動判定へ進む。 |
| 設定値の先頭文字が `0` | RAM 向けにする。文字列全体は parse しないため、`0`, `0anything` などが該当する。 |
| 空でなく、先頭文字が `0` 以外 | SSD 向けにする。例: `1`, `true`, `false`, `2`。大文字小文字、数値としての妥当性は検査しない。 |

ただし `STRATA_STAGER_THREADS` が設定されていると、この変数を読む分岐自体に入りません。スレッド数は `atoi` の結果を1～32に clamp して決めるため、`STRATA_STAGER_THREADS=0` や空文字でも1スレッドになります。変数名の「SSD」は設定値の先頭文字によるプロファイル選択を指し、SSD の有無を直接検出する処理ではありません。

## 有効になる条件

- `Prefill::init()` が stager をまだ持たず、stager の初期化を行うこと。
- source が存在し、少なくとも1つの `(layer, expert)` について `src->transient(l, e)` が true であること。
- `STRATA_STAGER_THREADS` が unset であること。

これらを満たさない場合は変数の値が使われません。特に、すべての expert が transient でない場合や、スレッド数を明示指定した場合には選択に影響しません。

自動判定で使われる `FileExpertSource::cached_share(256)` は Linux かつ mapped role file を持ち、mapping が有効で、サンプル数・モデル形状が有効な場合だけ `mincore` によるページ常駐率を返します。その他の platform/source、mapping 無効、または `mincore` 失敗などは `-1` となり、呼び出し側は SSD 向けプロファイルを維持します。明示値 `0` / 非 `0` による上書きはこの自動判定結果に依存しません。

## 実行時の詳細

`Prefill::init()` は source 全体を走査し、transient blob があるかを調べます。該当し、スレッド数が未指定なら、`STRATA_STAGER_SSD` を読みます。値が unset または空なら `cached_share(256)` による自動選択に進み、常駐率が90%以上の場合は RAM 向けにして stderr に次の形式で出します。

```text
prefill: the GGUF experts are <整数>% in the page cache; the stager takes the RAM profile
```

SSD 向けの場合、スレッド数は32です。RAM 向けの場合、`max(2, min(4, hardware_concurrency / 4))` で計算します（`hardware_concurrency()` が0なら2）。`STRATA_STAGER_THREADS` の明示値がある場合は上記のどちらの既定スレッド数にも優先します。

SSD 向けで `STRATA_STAGER_RING` が unset なら ring 深度はスレッド数の4倍です。`STRATA_STAGER_RING` が設定されていれば、stager 初期化内で `atoi` した値を2～256に clamp します。SSD 向けでない場合は変数未設定時の既定ring深度16が使われます。プロファイル選択は stager の作成時に一度行われ、作成済み stager の再利用中に環境を変更しても再評価されません。

## 根拠

- `src/prefill/prefill.cpp:1060-1065,1096-1103`: `Prefill::init()` と stager 初期化時期。
- `src/prefill/prefill.cpp:1104-1123`: transient source の走査、`STRATA_STAGER_THREADS` 優先、`STRATA_STAGER_SSD` の先頭文字判定、自動判定、スレッド既定値。
- `src/prefill/prefill.cpp:1124-1133,407-413,435-449`: ring 深度のプロファイル別既定と設定値の clamp、stager 初期化。
- `src/core/expert_source.cpp:2434-2442`: file source の `transient()` 判定。
- `src/core/expert_source.cpp:2444-2472`: Linux の `cached_share()`、サンプル方法、判定不能時の `-1`。
- `docs/DETAILS.md:1562`: GGUF read-in-place 用 stager の自動選択と `STRATA_STAGER_SSD=1` / `0` の説明。挙動の説明は実装と一致する。なお、ここにある性能比較は環境条件が十分特定されていないため、本調査では一般化した性能値として扱わない。
