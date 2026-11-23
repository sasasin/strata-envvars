# `STRATA_DFLASH2_TUNED_URL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は、Strata が取得する tuned DFlash2 drafter の**配布元**を指定する。未設定または空なら、通常の署名付き update feed から取得する。値があればその場所から直接取得し、feed の問い合わせを迂回する。直接取得でも、Strata が選んだ pack の固定サイズと SHA-256 は変更されないため、別の内容に差し替える指定ではない（`terminal/strata_control/drafting_fetch.py:301-326`、`terminal/strata_control/drafting.py:273-290,340-345`）。

対象は tuned pack が適用される DFlash2 の取得経路である。通常の stock DFlash2 pack の取得先を変えず、pack が既に検証済みで存在するときも取得先として参照されない（`terminal/strata_control/drafting_fetch.py:307-312,352-373`）。

## 値と判定

`ensure_tuned()` が `os.environ.get(..., "").strip()` で読み、前後の空白を除いた文字列を取得場所として使う。真偽値、数値、URL の全体形式をこの箇所では検証しない。空文字になれば feed 経路へ進む。大文字小文字を変換せず、`"0"` や `"false"` も偽値として扱われず、取得場所として試される（`terminal/strata_control/drafting_fetch.py:310-320`）。

| 条件 | unset | 値の例 | 空・無効な値の扱い |
|---|---|---|---|
| tuned pack を取得する必要があり、取得が許可される場合 | 既定の署名付き feed を検索 | `https://.../pack`、`file:///.../pack`、ローカルパス。直接取得先として使う | `""` と空白だけの値は `.strip()` 後に空となり、feed を検索。`"0"`・`"false"` はパス文字列として試される。未対応 scheme は transfer helper がエラーにする |

呼び出し側が `ensure_tuned(url=...)` に truthy な `url` を渡す場合は、その引数が環境変数より先に選ばれる。実際の `ensure_for()` 経路は `url` を渡さない。直接指定の有無にかかわらず、`selq4` は `339694592` bytes と SHA-256 `4df2…c664c`、`bf16sel` は `522458112` bytes と SHA-256 `34ca…cda9` を照合する（`terminal/strata_control/drafting_fetch.py:294-312`、`terminal/strata_control/drafting.py:273-282,340-345`）。

## 有効になる条件

- 呼び出し元が tuned drafter を使うモデルと実行環境を選び、`tuned_applies()` が真になること。対象表は Metal の `unsloth-ud-q4_k_xl` / `unsloth-ud-iq4_xs-v31`、CUDA の `iq3_s` / `unsloth-ud-iq4_xs-v31`（resident 条件。後者には streaming class の規則あり）、HIP の `iq3_s` と三つの指定 Unsloth set（先頭 architecture が `gfx1151`）、SYCL の `iq3_xxs`（`arc_a`）である。モデル set と backend、resident 判定や architecture が合わない場合、この変数を使う tuned 取得には進まず stock pack 経路になる（`terminal/strata_control/drafting.py:374-396,462-485`; 呼び出し: `terminal/strata_control/drafting_fetch.py:352-373`）。
- tuned pack がまだ検証済みの状態で存在しないこと。存在する場合は `ensure_tuned()` が環境変数を読む前にその pack を返す（`terminal/strata_control/drafting_fetch.py:301-312`）。
- 取得操作が許可されること。`acquisition.require()` は環境変数を読む前に実行され、`STRATA_NO_ACQUIRE` が `1` / `true` / `yes` / `on`（前後空白除去・小文字化）または acquisition 禁止区間内なら取得を拒否する（`terminal/strata_control/drafting_fetch.py:310-312`、`terminal/strata_control/acquisition.py:26-27,53-73`）。
- 選択先が transfer helper の扱える https、loopback または許可設定済みの http、`file:`、あるいはパスであること。Strata は URL 取得時もファイルサイズと SHA-256 を検査する（`terminal/strata_control/transfer.py:154-175,345-398`）。

## 実行時の詳細

環境変数はモジュール import 時ではなく、`ensure_tuned()` が呼ばれた都度読み取られるため、次回呼び出しまでにプロセス環境が変更されれば反映される。ただし検証済み tuned pack の早期 return、tuned 非適用の経路、取得禁止の経路ではこの値を読まない（`terminal/strata_control/drafting_fetch.py:301-312,352-373`）。

環境変数の値が非空なら Strata は `_reachable()` で場所を判定し、ローカル path / `file:` 以外は到達確認を行う。到達しない場合は tuned 取得を行わず `None` を返す。取得できた場合は `.part` に保存し、固定サイズと SHA-256 を確認してから tuned pack の保存先へ移す。検証失敗時は不正 pack を削除して `DraftingError` とし、stock pack は上書きしない（`terminal/strata_control/drafting_fetch.py:274-277,310-345`、`terminal/strata_control/transfer.py:345-398`）。

feed 経路で取得先が見つからない場合や、直接場所が到達不能で `None` になった場合、`ensure_for()` は利用可能な stock pack に戻り、なければ stock pack の取得を試す。明示的な `strata drafting fetch` は最終的に取得不能ならエラーとして扱う。一方、launch 経路は失敗を warning として通知し、モデルを継続する（`terminal/strata_control/drafting_fetch.py:315-373`、`terminal/strata_cli/drafting_cmd.py:281-305`、`terminal/strata_cli/launch/runner.py:2044-2087`）。

## ログと測定値

この変数の読み取り自体に専用ログはない。ダウンロードが始まると progress callback に `Downloading the tuned DFlash2 drafter…`、完了時に `The tuned DFlash2 drafter is ready.` を渡す。検証不一致時は `The tuned DFlash2 drafter did not pass the safety check, so it was deleted.` を `DraftingError` にする（`terminal/strata_control/drafting_fetch.py:326-345`）。CLI の明示取得がエラーになると stderr に `strata: {exc}` を出して終了コード 5 を返す（`terminal/strata_cli/drafting_cmd.py:295-301`）。launch では失敗文を warning として通知し、モデルは MTP または drafter なしで続行する（`terminal/strata_cli/launch/runner.py:2077-2087`）。

`docs/DETAILS.md` の DFlash2 節（`docs/DETAILS.md:1569-1573`）は tuned drafter の由来・ライセンスを説明するが、この環境変数による URL 選択の挙動は説明していないため、本書では実装を根拠とした。

## 根拠

- `terminal/strata_control/drafting.py:273-290,340-345,374-396,462-485`
- `terminal/strata_control/drafting_fetch.py:260-277,294-373`
- `terminal/strata_control/acquisition.py:26-27,53-73`
- `terminal/strata_control/transfer.py:154-175,345-398`
- `terminal/strata_cli/drafting_cmd.py:281-305`
- `terminal/strata_cli/launch/runner.py:2044-2087`
- `docs/DETAILS.md:1569-1573`
